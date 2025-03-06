import requests
import json
import os
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solders.keypair import Keypair
from solders.commitment_config import CommitmentLevel
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig





def send_local_create_tx(signer_private_key, token_name, token_symbol, description, image_path, twitter_link, telegram_link, website_link, initial_amount):
    signer_keypair = Keypair.from_base58_string(signer_private_key)

    # Generate a random keypair for token
    mint_keypair = Keypair()

    # Define token metadata
    form_data = {
        'name': token_name,
        'symbol': token_symbol,
        'description': description,
        'twitter': twitter_link,
        'telegram': telegram_link,
        'website': website_link,
        'showName': 'true'
    }

    # Read the image file from the provided image_path
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image file not found at path: {image_path}")

    with open(image_path, 'rb') as f:
        file_content = f.read()


    files = {
        'file': (os.path.basename(image_path), file_content, 'image/png')
    }

    # Create IPFS metadata storage
    metadata_response = requests.post("https://pump.fun/api/ipfs", data=form_data, files=files)
    metadata_response_json = metadata_response.json()

    # Token metadata
    token_metadata = {
        'name': form_data['name'],
        'symbol': form_data['symbol'],
        'uri': metadata_response_json['metadataUri']
    }

    # Generate the create transaction
    response = requests.post(
        "https://pumpportal.fun/api/trade-local",
        headers={'Content-Type': 'application/json'},
        data=json.dumps({
            'publicKey': str(signer_keypair.pubkey()),
            'action': 'create',
            'tokenMetadata': token_metadata,
            'mint': str(mint_keypair.pubkey()),
            'denominatedInSol': 'true',
            'amount': initial_amount,  # Use the provided initial amount
            'slippage': 10,
            'priorityFee': 0.0005,
            'pool': 'pump'
        })
    )

    if response.status_code != 200:
        raise ValueError(f"Failed to generate create transaction. Response: {response.content}")

    tx = VersionedTransaction(VersionedTransaction.from_bytes(response.content).message, [mint_keypair, signer_keypair])


    commitment = CommitmentLevel.Confirmed
    config = RpcSendTransactionConfig(preflight_commitment=commitment)
    txPayload = SendVersionedTransaction(tx, config)

    # Submit transaction to Solana blockchain
    solana_response = requests.post(
        url="https://api.mainnet-beta.solana.com/",
        headers={"Content-Type": "application/json"},
        data=SendVersionedTransaction(tx, config).to_json()
    )

    solana_response_json = solana_response.json()
    if solana_response.status_code != 200 or 'result' not in solana_response_json:
        raise ValueError(f"Failed to send transaction. Response: {solana_response.content}")

    txSignature = solana_response_json['result']
    print(f'Transaction: https://solscan.io/tx/{txSignature}')

    # Return the transaction signature and the token address
    return txSignature, str(mint_keypair.pubkey())


def sell_token(private_key, token_mint, amount, denominated_in_sol=True, slippage=10, priority_fee=0.005, pool="pump", rpc_endpoint="https://api.mainnet-beta.solana.com/"):
    """
    Realiza la venta de tokens utilizando la API de Pump Portal.
    
    Args:
        private_key (str): Clave privada en formato Base58.
        token_mint (str): Dirección del contrato del token a vender.
        amount (float): Cantidad de tokens o SOL a vender.
        denominated_in_sol (bool): Si `True`, la cantidad está en SOL; si `False`, en número de tokens.
        slippage (int): Porcentaje de slippage permitido.
        priority_fee (float): Fee de prioridad para la transacción.
        pool (str): El pool de intercambio a usar ("pump" o "raydium").
        rpc_endpoint (str): Endpoint RPC para enviar la transacción.
    
    Returns:
        str: Dirección de la transacción en Solscan.
    """
    try:
        # Crear el keypair desde la clave privada
        keypair = Keypair.from_base58_string(private_key)

        # Preparar la solicitud para la API de Pump Portal
        response = requests.post(
            url="https://pumpportal.fun/api/trade-local",
            json={
                "publicKey": str(keypair.pubkey()),
                "action": "sell",
                "mint": token_mint,
                "amount": amount,
                "denominatedInSol": str(denominated_in_sol).lower(),  # Convertir a "true" o "false"
                "slippage": slippage,
                "priorityFee": priority_fee,
                "pool": pool
            }
        )

        if response.status_code != 200:
            raise ValueError(f"Error en la API de Pump Portal: {response.content.decode()}")

        # Crear la transacción con la respuesta de la API
        tx = VersionedTransaction(
            VersionedTransaction.from_bytes(response.content).message,
            [keypair]
        )

        # Configurar el compromiso
        commitment = CommitmentLevel.Confirmed
        config = RpcSendTransactionConfig(preflight_commitment=commitment)
        tx_payload = SendVersionedTransaction(tx, config)

        # Enviar la transacción al nodo RPC
        solana_response = requests.post(
            url=rpc_endpoint,
            headers={"Content-Type": "application/json"},
            data=tx_payload.to_json()
        )

        solana_response_json = solana_response.json()
        if solana_response.status_code != 200 or "result" not in solana_response_json:
            raise ValueError(f"Error al enviar la transacción: {solana_response.content.decode()}")

        # Obtener la firma de la transacción
        tx_signature = solana_response_json["result"]
        print(f'Transaction: https://solscan.io/tx/{tx_signature}')
        return f'https://solscan.io/tx/{tx_signature}'

    except Exception as e:
        print(f"Error al vender tokens: {e}")
        return str(e)
