import telebot
from telebot import types
import requests
import os
import json
from solathon import Keypair, Client, PublicKey
from solders.transaction import VersionedTransaction
from solders.keypair import Keypair
from solders.commitment_config import CommitmentLevel
from solders.rpc.requests import SendVersionedTransaction
from solders.rpc.config import RpcSendTransactionConfig
from main2 import send_local_create_tx
import threading
import time

# Define el token de tu bot de Telegram
TOKEN = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
bot = telebot.TeleBot(TOKEN)
# Configura el cliente de Solana
client = Client("https://api.mainnet-beta.solana.com")

# Archivos para persistencia de datos
WALLETS_FILE = 'user_wallets.json'
TOKEN_DATA_FILE = 'user_token_data.json'
USER_STATES_FILE = 'user_states.json'

# Diccionarios para manejar datos
#user_wallets = {}
#user_token_data = {}
#user_states = {}

# Cargar datos desde archivos
def load_data():
    global user_wallets, user_token_data, user_states  # Declarar como globales

    def safe_load(file_path):
        try:
            if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                with open(file_path, 'r') as file:
                    return json.load(file)
            else:
                print(f"{file_path} no existe o está vacío. Inicializando como un diccionario vacío.")
        except json.JSONDecodeError:
            print(f"Advertencia: {file_path} no es un archivo JSON válido. Se inicializará como un diccionario vacío.")
        return {}

    # Solo cargar datos si los archivos tienen contenido válido
    user_wallets = safe_load(WALLETS_FILE)
    user_token_data = safe_load(TOKEN_DATA_FILE)
    user_states = safe_load(USER_STATES_FILE)

    print("Datos cargados correctamente:")
    print("Wallets:", user_wallets)
    print("Tokens:", user_token_data)
    print("Estados:", user_states)

# Guardar datos en archivos
def save_data():
    global user_wallets, user_token_data, user_states  # Declarar como globales

    if not user_wallets and not user_token_data and not user_states:
        print("Advertencia: Intento de guardar datos vacíos. No se realizará ninguna operación.")
        return

    with open(WALLETS_FILE, 'w') as file:
        json.dump(user_wallets, file)
    with open(TOKEN_DATA_FILE, 'w') as file:
        json.dump(user_token_data, file)
    with open(USER_STATES_FILE, 'w') as file:
        json.dump(user_states, file)
    print("Datos guardados correctamente.")

# Guardado automático de datos cada 60 segundos
def auto_save():
    while True:
        save_data()
        time.sleep(60)

# Iniciar el guardado automático en un hilo separado
threading.Thread(target=auto_save, daemon=True).start()

# Cargar datos al iniciar
load_data()

# Comando /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = str(message.from_user.id)
    user_states[user_id] = "start"
    markup = types.InlineKeyboardMarkup()
    create_wallet_button = types.InlineKeyboardButton("⚙️ Create a Wallet", callback_data="create_wallet")
    import_wallet_button = types.InlineKeyboardButton("📥 Import Solana Wallet", callback_data="import_wallet")
    markup.add(create_wallet_button, import_wallet_button)
    image_welcome = "./1.png"
    bot.send_photo(
        message.chat.id,
        photo=open(image_welcome, "rb"),
        caption= 
                f"Welcome to Pump Agent Assistant.\n"
                f"Use the following commands:\n\n"
                f"/launch - Start the launch process\n"
                f"/buy - to buy a token\n"
                f"/sell - to sell a token\n"
                f"/wallet - Show your wallet balance", 
        reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "import_wallet")
def import_wallet_start(call):
    user_id = str(call.from_user.id)
    user_states[user_id] = "import_wallet"
    msg = bot.send_message(call.message.chat.id, "Please enter your private key:")
    bot.register_next_step_handler(msg, process_private_key)

def process_private_key(message):
    user_id = str(message.from_user.id)
    private_key_base58 = message.text.strip()

    try:
        keypair = Keypair.from_private_key(private_key_base58)
        public_key = str(keypair.public_key)
        balance = get_wallet_balance(public_key)

        user_wallets[user_id] = {
            'public_key': public_key,
            'private_key': private_key_base58,
            'api_key': None
        }
        save_data()

        bot.send_message(
            message.chat.id,
            f"✅ Wallet imported successfully.\n\n"
            f"🔑 *Public key:* `{public_key}`\n"
            f"💰 *Balance:* {balance:.6f} SOL",
            parse_mode="Markdown"
        )
        user_states[user_id] = None

    except Exception as e:
        bot.send_message(
            message.chat.id, f"❌ An error occurred while processing the private key: {e}"
        )

@bot.callback_query_handler(func=lambda call: call.data == "create_wallet")
def create_wallet(call):
    user_id = str(call.from_user.id)
    if user_id in user_wallets:
        bot.send_message(call.message.chat.id, "You already have a wallet. Use the /wallet command to view it.")
        return
    try:
        response = requests.get("https://pumpportal.fun/api/create-wallet")
        if response.status_code == 200:
            wallet_data = response.json()
            if all(key in wallet_data for key in ('walletPublicKey', 'privateKey', 'apiKey')):
                wallet_public_key = wallet_data['walletPublicKey']
                private_key = wallet_data['privateKey']
                api_key = wallet_data['apiKey']

                user_wallets[user_id] = {
                    'public_key': wallet_public_key,
                    'private_key': private_key,
                    'api_key': api_key
                }
                save_data()

                bot.send_message(
                    call.message.chat.id,
                    f"✅ Wallet created.\n\n\🔑 *Public Key:* `{wallet_public_key}`",
                    f"*Private key:* `{private_key}`",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(call.message.chat.id, "❌ API response missing expected keys.")
        else:
            bot.send_message(call.message.chat.id, f"❌ Error creating wallet: {response.status_code}")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ An error occurred: {e}")

def get_wallet_balance(public_key):
    """
    Obtiene el balance de una wallet en la red Solana utilizando Solathon.
    Args:
        public_key (str): Clave pública de la wallet.

    Returns:
        float: Balance en SOL.
    """
    try:
        # Convertir la clave pública en objeto PublicKey si es necesario
        public_key_obj = PublicKey(public_key)
        # Obtener el balance en lamports
        lamports = client.get_balance(public_key_obj)
        # Convertir lamports a SOL
        return lamports / 1_000_000_000
    except Exception as e:
        print(f"Error al obtener el balance de la wallet: {e}")
        return 0.0
    
@bot.message_handler(commands=['wallet'])
def show_wallet_info(message):
    global user_wallets
    user_id = str(message.from_user.id)
    wallet_info = user_wallets.get(user_id)

    if not wallet_info:
        bot.send_message(message.chat.id, "❌ You do not have a wallet. Use the /start command to create one.")
        return

    public_key = wallet_info['public_key']
    private_key = wallet_info['private_key']
    sol_balance = get_wallet_balance(public_key)

    # Construir mensaje de respuesta
    response_message = (
        f"🔑 *Public Key:* `{public_key}`\n"
        f"🔑 *Private Key:* `{private_key}`\n"
        f"💰 *SOL Balance:* {sol_balance:.6f} SOL"
    )

    bot.send_message(message.chat.id, response_message, parse_mode="Markdown")

# Comando /buy para iniciar el proceso de compra de un token
@bot.message_handler(commands=['buy'])
def buy_token_command(message):
    """
    Inicia el proceso de compra del token pidiendo al usuario el token mint y la cantidad.
    """
    user_id = str(message.from_user.id)
    wallet_info = user_wallets.get(user_id)

    if not wallet_info:
        bot.send_message(message.chat.id, "❌ You do not have a wallet. Use the /start command to create one.")
        return

    msg = bot.send_message(message.chat.id, "Please enter the token mint (address) of the token you want to buy:")
    bot.register_next_step_handler(msg, process_buy_token_mint)

def process_buy_token_mint(message):
    """
    Solicita al usuario la cantidad de tokens a comprar.
    """
    user_id = str(message.from_user.id)
    token_mint = message.text.strip()

    if not token_mint or len(token_mint) != 44:
        bot.send_message(message.chat.id, "❌ Invalid token mint format. Please enter a valid token address.")
        return

    user_states[user_id] = {'token_mint': token_mint}

    msg = bot.send_message(message.chat.id, "Enter the amount of tokens you want to buy:")
    bot.register_next_step_handler(msg, process_buy_amount)

def process_buy_amount(message):
    """
    Procesa la compra del token utilizando el token mint y la cantidad proporcionada por el usuario.
    """
    user_id = str(message.from_user.id)
    wallet_info = user_wallets.get(user_id)
    token_mint = user_states[user_id].get('token_mint')
    amount = message.text.strip()

    try:
        # Validar la cantidad
        amount = float(amount)
        if amount <= 0:
            raise ValueError("Amount must be greater than 0.")

        private_key = wallet_info['private_key']
        public_key = wallet_info['public_key']

        # Hacer la llamada a la API de Pump Portal
        response = requests.post(
            url="https://pumpportal.fun/api/trade-local",
            json={
                "publicKey": public_key,
                "action": "buy",
                "mint": token_mint,
                "amount": amount,
                "denominatedInSol": "false",
                "slippage": 10,
                "priorityFee": 0.005,
                "pool": "pump"
            }
        )

        # Validar respuesta de la API
        if response.status_code != 200:
            bot.send_message(message.chat.id, f"❌ Error in Pump Portal API: {response.text}")
            return

        # Procesar la transacción
        keypair = Keypair.from_base58_string(private_key)
        tx = VersionedTransaction(VersionedTransaction.from_bytes(response.content).message, [keypair])
        commitment = CommitmentLevel.Confirmed
        config = RpcSendTransactionConfig(preflight_commitment=commitment)
        tx_payload = SendVersionedTransaction(tx, config)

        rpc_response = requests.post(
            url="https://api.mainnet-beta.solana.com/",
            headers={"Content-Type": "application/json"},
            data=tx_payload.to_json()
        )

        # Extraer el resultado
        rpc_result = rpc_response.json()
        if "result" in rpc_result:
            tx_signature = rpc_result['result']
            bot.send_message(
                message.chat.id,
                f"✅ Tokens successfully purchased!\n\n🔗 Transaction: [View on Solscan](https://solscan.io/tx/{tx_signature})",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                message.chat.id,
                f"❌ Error in transaction: {rpc_result.get('error', {}).get('message', 'Unknown error')}"
            )
    except ValueError as ve:
        bot.send_message(message.chat.id, f"❌ Invalid input: {ve}")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ An error occurred while purchasing tokens: {e}")

def send_long_message(chat_id, message, bot_instance):
    """
    Envía un mensaje largo dividiéndolo en fragmentos si excede el límite permitido por Telegram.

    Args:
        chat_id (int): ID del chat de Telegram.
        message (str): Mensaje a enviar.
        bot_instance (TeleBot): Instancia del bot de Telegram.
    """
    max_length = 4096  # Límite de caracteres permitido por Telegram
    for i in range(0, len(message), max_length):
        bot_instance.send_message(chat_id, message[i:i + max_length], parse_mode="Markdown")

# Comando /sell para iniciar el proceso de venta de un token
@bot.message_handler(commands=['sell'])
def sell_token_command(message):
    """
    Inicia el proceso de venta del token pidiendo al usuario que proporcione el token mint.
    """
    user_id = str(message.from_user.id)
    wallet_info = user_wallets.get(user_id)

    if not wallet_info:
        bot.send_message(message.chat.id, "❌ You do not have a wallet. Use the /start command to create one.")
        return

    msg = bot.send_message(message.chat.id, "Please enter the token mint (address) of the token you want to sell:")
    bot.register_next_step_handler(msg, process_token_sell)

def process_token_sell(message):
    """
    Procesa la venta del token utilizando el token mint proporcionado por el usuario.
    """
    user_id = str(message.from_user.id)
    wallet_info = user_wallets.get(user_id)
    token_mint = message.text.strip()

    if not wallet_info:
        bot.send_message(message.chat.id, "❌ You do not have a wallet. Use the /start command to create one.")
        return

    private_key = wallet_info['private_key']
    public_key = wallet_info['public_key']

    try:
        # Hacer la llamada a la API de Pump Portal
        response = requests.post(
            url="https://pumpportal.fun/api/trade-local",
            json={
                "publicKey": public_key,
                "action": "sell",
                "mint": token_mint,
                "amount": "100%",  # Vender el 100% de los tokens
                "denominatedInSol": "false",
                "slippage": 10,
                "priorityFee": 0.005,
                "pool": "pump"
            }
        )

        # Validar respuesta de la API
        if response.status_code != 200:
            bot.send_message(message.chat.id, f"❌ Error in Pump Portal API: {response.text}")
            return

        # Procesar la transacción
        keypair = Keypair.from_base58_string(private_key)
        tx = VersionedTransaction(VersionedTransaction.from_bytes(response.content).message, [keypair])
        commitment = CommitmentLevel.Confirmed
        config = RpcSendTransactionConfig(preflight_commitment=commitment)
        tx_payload = SendVersionedTransaction(tx, config)

        rpc_response = requests.post(
            url="https://api.mainnet-beta.solana.com/",
            headers={"Content-Type": "application/json"},
            data=tx_payload.to_json()
        )

        # Extraer el resultado
        rpc_result = rpc_response.json()
        if "result" in rpc_result:
            tx_signature = rpc_result['result']
            bot.send_message(
                message.chat.id,
                f"✅ Tokens successfully sold!\n\n🔗 Transaction: [View on Solscan](https://solscan.io/tx/{tx_signature})",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                message.chat.id,
                f"❌ Error in transaction: {rpc_result.get('error', {}).get('message', 'Unknown error')}"
            )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ An error occurred while selling tokens: {e}")

# maneja el porcentaje de venta
@bot.callback_query_handler(func=lambda call: call.data.startswith("sell_percentage"))
def process_sell_percentage(call):
    """
    Procesa la venta de tokens basada en el porcentaje seleccionado por el usuario.

    Args:
        call: Objeto de callback de Telegram.
    """
    try:
        # Obtener datos del usuario y la wallet
        user_id = str(call.from_user.id)
        wallet_info = user_wallets.get(user_id)
        if not wallet_info:
            bot.send_message(call.message.chat.id, "❌ You do not have a wallet. Use the /start command to create one.")
            return

        # Parsear el callback data para obtener el token y porcentaje
        _, token_address, percentage = call.data.split("|")
        private_key = wallet_info['private_key']
        public_key = wallet_info['public_key']

        # Calcular el porcentaje
        amount = f"{percentage}%"  # Usar directamente el porcentaje recibido

        # Hacer la llamada a la API de Pump Portal
        response = requests.post(
            url="https://pumpportal.fun/api/trade-local",
            json={
                "publicKey": public_key,
                "action": "sell",
                "mint": token_address,
                "amount": amount,  # Porcentaje especificado
                "denominatedInSol": "false",
                "slippage": 10,
                "priorityFee": 0.005,
                "pool": "pump"
            }
        )

        # Validar respuesta de la API
        if response.status_code != 200:
            bot.send_message(call.message.chat.id, f"❌ Error in Pump Portal API: {response.text}")
            return

        # Construir y enviar la transacción
        keypair = Keypair.from_base58_string(private_key)
        tx = VersionedTransaction(VersionedTransaction.from_bytes(response.content).message, [keypair])
        commitment = CommitmentLevel.Confirmed
        config = RpcSendTransactionConfig(preflight_commitment=commitment)
        tx_payload = SendVersionedTransaction(tx, config)

        rpc_response = requests.post(
            url="https://api.mainnet-beta.solana.com/",
            headers={"Content-Type": "application/json"},
            data=tx_payload.to_json()
        )

        # Procesar la respuesta de la transacción RPC
        rpc_result = rpc_response.json()
        if "result" in rpc_result:
            tx_signature = rpc_result['result']
            bot.send_message(
                call.message.chat.id,
                f"✅ Tokens successfully sold!\n\n🔗 Transaction: [View on Solscan](https://solscan.io/tx/{tx_signature})",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                call.message.chat.id,
                f"❌ Error in transaction: {rpc_result.get('error', {}).get('message', 'Unknown error')}"
            )
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ An error occurred while selling tokens: {e}")

 

# Comando /launch para iniciar el proceso de lanzamiento de un nuevo token
@bot.message_handler(commands=['launch'])
def launch_token(message):
    user_id = str(message.from_user.id)
    if user_id not in user_wallets:
        bot.send_message(message.chat.id, "You do not have a wallet created. Use the /start command to create one.")
        return

    msg = bot.send_message(message.chat.id, "Please enter the name of the token:")
    bot.register_next_step_handler(msg, process_token_name)

def process_token_name(message):
    user_id = str(message.from_user.id)
    user_token_data[user_id] = {'name': message.text}
    msg = bot.send_message(message.chat.id, "Enter the token symbol:")
    bot.register_next_step_handler(msg, process_token_symbol)

def process_token_symbol(message):
    user_id = str(message.from_user.id)
    user_token_data[user_id]['symbol'] = message.text
    msg = bot.send_message(message.chat.id, "Provide the token image URL:")
    bot.register_next_step_handler(msg, process_token_image)

def process_token_image(message):
    user_id = str(message.from_user.id)
    user_token_data[user_id]['image'] = message.text
    msg = bot.send_message(message.chat.id, "Provide the token website URL:")
    bot.register_next_step_handler(msg, process_token_website)

def process_token_website(message):
    user_id = str(message.from_user.id)
    user_token_data[user_id]['website'] = message.text
    msg = bot.send_message(message.chat.id, "Provide the Telegram URL:")
    bot.register_next_step_handler(msg, process_token_telegram)

def process_token_telegram(message):
    user_id = str(message.from_user.id)
    user_token_data[user_id]['telegram'] = message.text
    msg = bot.send_message(message.chat.id, "Provide the Twitter URL:")
    bot.register_next_step_handler(msg, process_token_twitter)

def process_token_twitter(message):
    user_id = str(message.from_user.id)
    user_token_data[user_id]['twitter'] = message.text
    msg = bot.send_message(message.chat.id, "Enter the initial purchase amount (in SOL):")
    bot.register_next_step_handler(msg, process_token_initial_amount)


def process_token_initial_amount(message):
    user_id = str(message.from_user.id)
    try:
        initial_amount = float(message.text.strip())
        if initial_amount <= 0:
            raise ValueError("Amount must be positive.")

        user_token_data[user_id]['initial_amount'] = initial_amount

        token_data = user_token_data[user_id]
        response_message = (
            f"🤖 You are about to launch a token with the following details:\n\n"
            f"🪙 *Name:* {token_data['name']}\n"
            f"💲 *Symbol:* {token_data['symbol']}\n"
            f"🖼️ *Image:* [View Image]({token_data['image']})\n"
            f"🌐 *Website:* {token_data['website']}\n"
            f"📢 *Telegram:* {token_data['telegram']}\n"
            f"🐦 *Twitter:* {token_data['twitter']}\n"
            f"💰 *Initial Amount:* {token_data['initial_amount']} SOL\n\n"
            f"If the information is correct, press Confirm Launch."
        )

        markup = types.InlineKeyboardMarkup()
        confirm_button = types.InlineKeyboardButton("🦾 Confirm Launch", callback_data="confirm_launch")
        markup.add(confirm_button)

        bot.send_message(message.chat.id, response_message, parse_mode="Markdown", reply_markup=markup)

    except ValueError:
        bot.send_message(message.chat.id, "❌ Invalid amount. Please enter a positive number.")
        msg = bot.send_message(message.chat.id, "Enter the initial purchase amount (in SOL):")
        bot.register_next_step_handler(msg, process_token_initial_amount)


@bot.callback_query_handler(func=lambda call: call.data == "confirm_launch")
def confirm_launch(call):
    global user_wallets, user_token_data
    user_id = str(call.from_user.id)
    token_data = user_token_data.get(user_id)
    wallet_info = user_wallets.get(user_id)

    if not wallet_info or not token_data:
        bot.send_message(call.message.chat.id, "❌ Missing wallet or token data. Please restart the process.")
        return

    private_key = wallet_info['private_key']
    initial_amount = token_data.get('initial_amount', 0.001)  # Usa el monto ingresado por el usuario o un valor por defecto.
    # Descargar la imagen
    image_path = None 

    try:
        # Descargar la imagen del token
        image_response = requests.get(token_data['image'], stream=True)
        if image_response.status_code == 200:
            image_path = f"/tmp/{user_id}_token_image.png"
            with open(image_path, 'wb') as f:
                for chunk in image_response.iter_content(1024):
                    f.write(chunk)
        else:
            bot.send_message(call.message.chat.id, "❌ Failed to download the image. Check the image URL.")
            return

        # Intentar lanzar el token
        transaction_signature, token_address = send_local_create_tx(
            signer_private_key=private_key,
            token_name=token_data['name'],
            token_symbol=token_data['symbol'],
            description=f"Token {token_data['name']} created via Pump Assistant🤖",
            image_path=image_path,
            twitter_link=token_data['twitter'],
            telegram_link=token_data['telegram'],
            website_link=token_data['website'],
            initial_amount=initial_amount  # Incluye el argumento inicial.
        )

        # Guardar datos del token lanzado
        user_token_data[user_id]['last_token_address'] = token_address
        save_data()

        # Confirmar lanzamiento exitoso
        bot.send_message(
            call.message.chat.id,
            f"✅ Token successfully launched!\n\n"
            f"🔗 Transaction: [View on Solscan](https://solscan.io/tx/{transaction_signature})\n"
            f"📃 Token Address: `{token_address}`",
            parse_mode="Markdown"
        )

        # Mostrar opciones para vender tokens
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("50%", callback_data=f"sell_percentage|{token_address}|50"),
            types.InlineKeyboardButton("75%", callback_data=f"sell_percentage|{token_address}|75"),
            types.InlineKeyboardButton("100%", callback_data=f"sell_percentage|{token_address}|100")
        )
        bot.send_message(
            call.message.chat.id,
            "Select the percentage of tokens you want to sell:",
            reply_markup=markup
        )

    except ValueError as ve:
        # Analizar el error para identificar problemas específicos
        if "InsufficientFundsForRent" in str(ve):
            bot.send_message(
                call.message.chat.id,
                "❌ Insufficient funds for rent.\n\n"
                "Please ensure your wallet has enough SOL to cover the rent required for the new token accounts. "
                "Typically, you need at least 0.01 SOL per new account."
            )
        else:
            # Limitar la longitud del mensaje de error para cumplir con los límites de Telegram
            error_message = str(ve)[:500]  # Limitar a los primeros 500 caracteres
            bot.send_message(
                call.message.chat.id,
                f"❌ Launch error: {error_message}\n\n"
                "Please check your inputs or wallet balance and try again."
            )
        # Registrar el error completo en la consola
        print(f"Full ValueError: {ve}")

    except requests.exceptions.RequestException:
        bot.send_message(call.message.chat.id, "❌ Failed to download the image. Check your internet connection.")
    
    except KeyError as ke:
        bot.send_message(call.message.chat.id, f"❌ Missing required data: {ke}")

    except Exception as e:
        # Clasificar errores comunes y simplificar el mensaje
        error_message = str(e)
        if "Transaction simulation failed" in error_message:
            bot.send_message(call.message.chat.id, "❌ Transaction simulation failed. Check your wallet balance or inputs.")
        elif "insufficient funds" in error_message:
            bot.send_message(call.message.chat.id, "❌ Insufficient funds in your wallet. Please deposit SOL.")
        elif "Invalid account" in error_message:
            bot.send_message(call.message.chat.id, "❌ Invalid account data. Verify the wallet and token details.")
        else:
            bot.send_message(call.message.chat.id, f"❌ An unexpected error occurred: {error_message[:500]}")

    finally:
        # Limpiar archivo temporal de la imagen
        if image_path and os.path.exists(image_path):
            os.remove(image_path)


if __name__ == '__main__':
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

