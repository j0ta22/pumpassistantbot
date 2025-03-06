import telebot
from telebot import types
import requests
import os
import json
from solathon import Keypair
from main2 import send_local_create_tx

# Define el token de tu bot de Telegram
TOKEN = '7725298185:AAGgV2fBniVZwQ4GlFUM9OV_Hyb_XaPgn54'
bot = telebot.TeleBot(TOKEN)

# Archivo donde se almacenarán las wallets
WALLETS_FILE = 'user_wallets.json'

# Diccionarios para almacenar datos de usuarios
user_wallets = {}
user_token_data = {}

# Función para cargar las wallets desde el archivo JSON
def load_wallets():
    global user_wallets
    if os.path.exists(WALLETS_FILE):
        with open(WALLETS_FILE, 'r') as file:
            user_wallets = json.load(file)

# Función para guardar las wallets en el archivo JSON
def save_wallets():
    with open(WALLETS_FILE, 'w') as file:
        json.dump(user_wallets, file)

# Cargar las wallets al iniciar el bot
load_wallets()

# Comando /start con botón para crear una nueva wallet de Solana
@bot.message_handler(commands=['start'])
def send_welcome(message):
    markup = types.InlineKeyboardMarkup()
    create_wallet_button = types.InlineKeyboardButton("⚙️ Create a Wallet", callback_data="create_wallet")
    import_wallet_button = types.InlineKeyboardButton("📥 Import Solana Wallet", callback_data="import_wallet")
    markup.add(create_wallet_button, import_wallet_button)
    bot.send_message(message.chat.id, "Welcome! Use the buttons below to manage your wallets.", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == "import_wallet")
def import_wallet_start(call):
    msg = bot.send_message(call.message.chat.id, "Please enter your private key:")
    bot.register_next_step_handler(msg, process_private_key)

def process_private_key(message):
    user_id = str(message.from_user.id)
    private_key_base58 = message.text.strip()

    try:
        # Crear un Keypair desde la clave privada
        keypair = Keypair.from_private_key(private_key_base58)
        public_key = str(keypair.public_key) 

        # Consultar el balance de la wallet
        balance = get_wallet_balance(public_key)

        # Guardar la wallet en el archivo local
        user_wallets[user_id] = {
            'public_key': public_key,
            'private_key': private_key_base58,
            'api_key': None  # Si no necesitas un API key, puedes dejarlo como None
        }
        save_wallets()

        bot.send_message(
            message.chat.id,
            f"✅Wallet imported successfully.\n\n"
            f"🔑 *Public key:* `{public_key}`\n"
            f"💰 *Balance:* {balance:.6f} SOL",
            parse_mode="Markdown"
        )

    except ValueError:
        bot.send_message(
            message.chat.id,
            "❌The private key entered is invalid. Please check the format and try again."
        )
    except Exception as e:
        bot.send_message(message.chat.id, f"❌An error occurred while processing the private key: {e}")


# Manejo del botón para crear una nueva wallet
@bot.callback_query_handler(func=lambda call: call.data == "create_wallet")
def create_wallet(call):
    user_id = str(call.from_user.id)
    if user_id in user_wallets:
        bot.send_message(call.message.chat.id, "You now have a wallet created. Use the /wallet command to view it or issue a new token.")
        return
    try:
        # Realizar la solicitud para crear una nueva wallet
        response = requests.get("https://pumpportal.fun/api/create-wallet")
        
        # Verificar si la solicitud fue exitosa
        if response.status_code == 200:
            wallet_data = response.json()
            
            # Verificar que la respuesta contenga las claves esperadas
            if all(key in wallet_data for key in ('walletPublicKey', 'privateKey', 'apiKey')):
                wallet_public_key = wallet_data['walletPublicKey']
                private_key = wallet_data['privateKey']
                api_key = wallet_data['apiKey']
                
                # Almacenar la clave privada de forma segura asociada al usuario
                user_wallets[user_id] = {
                    'public_key': wallet_public_key,
                    'private_key': private_key,
                    'api_key': api_key
                }

                # Guardar las wallets en el archivo JSON
                save_wallets()
                
                # Asumir que el balance inicial es 0 SOL
                balance = 0.0
                
                response_message = (
                    f"🟢A new Solana wallet has been created.\n\n"
                    f"🔑 *Public Key:* `{wallet_public_key}`\n"
                    f"💰 *Balance:* {balance} SOL\n\n"
                    f"🚀Use the button below to launch a new token on pump.fun"
                )
                
                # Crear botón para lanzar un nuevo token
                markup = types.InlineKeyboardMarkup()
                launch_token_button = types.InlineKeyboardButton("Launch a new token on pump.fun", callback_data="launch_token")
                markup.add(launch_token_button)
                
                bot.send_message(call.message.chat.id, response_message, parse_mode="Markdown", reply_markup=markup)
            else:
                bot.send_message(call.message.chat.id, "The API response does not contain the expected keys.")
        else:
            bot.send_message(call.message.chat.id, f"Error creating wallet. Status code: {response.status_code}")
    except requests.exceptions.RequestException as e:
        bot.send_message(call.message.chat.id, f"Error in HTTP request: {e}")
    except ValueError:
        bot.send_message(call.message.chat.id, "Error decoding JSON response.")
    except Exception as e:
        bot.send_message(call.message.chat.id, f"An unexpected error occurred: {e}")

import requests

def get_wallet_balance(public_key):
    """
    Obtiene el balance de una wallet en la red Solana.
    Args:
        public_key (str): Clave pública de la wallet.

    Returns:
        float: Balance en SOL.
    """
    try:
        rpc_url = "https://api.mainnet-beta.solana.com/"
        headers = {"Content-Type": "application/json"}
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getBalance",
            "params": [public_key]
        }

        response = requests.post(rpc_url, json=payload, headers=headers)
        response_data = response.json()

        # Imprimir la respuesta del RPC para depuración
        print("RPC Response:", response_data)

        # Verificar y retornar el balance en SOL
        lamports = response_data.get("result", {}).get("value", 0)
        return lamports / 1_000_000_000  # Convertir lamports a SOL
    except Exception as e:
        print(f"Error getting wallet balance: {e}")
        return 0.0  # Si hay un error, retornar 0 SOL


# Comando /wallet para mostrar la dirección pública y el balance
@bot.message_handler(commands=['wallet'])
def show_wallet_info(message):
    user_id = str(message.from_user.id)
    wallet_info = user_wallets.get(user_id)

    if wallet_info:
        public_key = wallet_info['public_key']
        # Aquí deberías implementar la lógica para obtener el balance actual de la wallet###################################
        balance = get_wallet_balance(public_key)

        response_message = (
            f"Información de tu wallet de Solana:\n\n"
            f"🔑 *Clave Pública:* `{public_key}`\n"
            f"💰 *Balance:* {balance:.6f} SOL"
        )
        bot.send_message(message.chat.id, response_message, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "You do not have a wallet created. Use the /start command to create one.")

# Función para obtener el balance de una wallet (debes implementarla)
def get_wallet_balance(public_key):
    # Implementa la lógica para consultar el balance de la wallet utilizando la API de Solana
    # Por ejemplo, puedes usar una API pública o una librería específica de Solana
    # Retorna el balance como un número flotante
    return 0.0  # Placeholder

# Comando /launch para iniciar el proceso de lanzamiento de un nuevo token
@bot.message_handler(commands=['launch'])
def launch_token(message):
    user_id = str(message.from_user.id)
    if user_id not in user_wallets:
        bot.send_message(message.chat.id, "You do not have a wallet created. Use the /start command to create one.")
        return

    msg = bot.send_message(message.chat.id, "Please enter the name of the token:")
    bot.register_next_step_handler(msg, process_token_name)

# Manejo del proceso para lanzar un nuevo token
@bot.callback_query_handler(func=lambda call: call.data == "launch_token")
def request_token_name(call):
    msg = bot.send_message(call.message.chat.id, "Please enter the name of the token:")
    bot.register_next_step_handler(msg, process_token_name)

def process_token_name(message):
    user_id = str(message.from_user.id)
    user_token_data[user_id] = {'name': message.text}
    msg = bot.send_message(message.chat.id, "Enter the token symbol:")
    bot.register_next_step_handler(msg, process_token_symbol)

def process_token_symbol(message):
    user_id = str(message.from_user.id)
    user_token_data[user_id]['symbol'] = message.text
    msg = bot.send_message(message.chat.id, "Provides the link of the token image:")
    bot.register_next_step_handler(msg, process_token_image)

def process_token_image(message):
    user_id = str(message.from_user.id)
    user_token_data[user_id]['image'] = message.text
    msg = bot.send_message(message.chat.id, "Provides the token web page link:")
    bot.register_next_step_handler(msg, process_token_website)

def process_token_website(message):
    user_id = str(message.from_user.id)
    user_token_data[user_id]['website'] = message.text
    msg = bot.send_message(message.chat.id, "Provide the Telegram link of the token:")
    bot.register_next_step_handler(msg, process_token_telegram)

def process_token_telegram(message):
    user_id = str(message.from_user.id)
    user_token_data[user_id]['telegram'] = message.text
    msg = bot.send_message(message.chat.id, "Provide the Twitter link of the token:")
    bot.register_next_step_handler(msg, process_token_twitter)

def process_token_twitter(message):
    user_id = str(message.from_user.id)
    user_token_data[user_id]['twitter'] = message.text

    # Mostrar resumen y botón para confirmar lanzamiento
    token_data = user_token_data[user_id]
    response_message = (
        f"⚠️You are about to launch a new token with the following details:\n\n"
        f"🪙 *Name:* {token_data['name']}\n"
        f"💲 *Symbol:* {token_data['symbol']}\n"
        f"🖼️ *Image:* [Ver Imagen]({token_data['image']})\n"
        f"🌐 *Website:* {token_data['website']}\n"
        f"📢 *Telegram:* {token_data['telegram']}\n"
        f"🐦 *Twitter:* {token_data['twitter']}\n\n"
        f"If all the information is correct, press the button below to launch the token."
    )

    markup = types.InlineKeyboardMarkup()
    confirm_launch_button = types.InlineKeyboardButton("⚠️Confirm launch", callback_data="confirm_launch")
    markup.add(confirm_launch_button)

    bot.send_message(message.chat.id, response_message, parse_mode="Markdown", reply_markup=markup)

# Confirmación y ejecución del lanzamiento del token
@bot.callback_query_handler(func=lambda call: call.data == "confirm_launch")
def confirm_launch(call):
    user_id = call.from_user.id
    token_data = user_token_data.get(user_id)
    private_key_base58 = user_wallets.get(user_id)

    if token_data and private_key_base58:
        image_path = None
        try:
            # Descargar la imagen desde la URL proporcionada
            image_response = requests.get(token_data['image'])
            if image_response.status_code == 200:
                image_path = f"/tmp/{user_id}_token_image.png"
                with open(image_path, 'wb') as f:
                    f.write(image_response.content)
            else:
                bot.send_message(call.message.chat.id, "❌The image could not be downloaded from the provided URL.")
                return

            # Llamar a la función para crear y lanzar el token
            transaction_signature, token_address = send_local_create_tx(
                signer_private_key=private_key_base58,
                token_name=token_data['name'],
                token_symbol=token_data['symbol'],
                description=f"🤖Token {token_data['name']} launched via the Pump Agent Assistant.",
                image_path=image_path,
                twitter_link=token_data['twitter'],
                telegram_link=token_data['telegram'],
                website_link=token_data['website']
            )

            import requests

            def confirm_transaction(tx_signature):
                """
                Verifica si una transacción en la red Solana fue confirmada.

                Args:
                    tx_signature (str): La firma de la transacción que se va a confirmar.

                Returns:
                    bool: True si la transacción está confirmada, False de lo contrario.
                """
                try:
                    rpc_url = "https://api.mainnet-beta.solana.com/"
                    headers = {"Content-Type": "application/json"}
                    payload = {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "getSignatureStatuses",
                        "params": [[tx_signature], {"searchTransactionHistory": True}]
                    }

                    response = requests.post(rpc_url, json=payload, headers=headers)
                    response_data = response.json()

                    # Verifica el estado de la transacción
                    status = response_data.get("result", {}).get("value", [])[0]
                    if status and status.get("confirmationStatus") == "confirmed":
                        return True
                    return False
                except Exception as e:
                    print(f"❌Error verifying transaction: {e}")
                    return False


            # Confirmar la transacción
            confirmation = confirm_transaction(transaction_signature)
            if confirmation:
                bot.send_message(call.message.chat.id, f"✅Token launched successfully. Token address: {token_address}")
            else:
                bot.send_message(call.message.chat.id, "❌Error confirming transaction.")
        except Exception as e:
            bot.send_message(call.message.chat.id, f"❌An error occurred during token launch: {e}")
        finally:
            # Limpiar archivos temporales
            if image_path and os.path.exists(image_path):
                os.remove(image_path)
    else:
        bot.send_message(call.message.chat.id, "❌No token or wallet data found. Please start the process again.")

 
if __name__ == '__main__':
    print('Iniciando el bot')
    bot.polling()
    print('fin')