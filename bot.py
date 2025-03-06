import telebot
from telebot import types
import requests
import os
import json
from solathon import Keypair, Client, PublicKey
from main2 import send_local_create_tx, sell_token
import threading
import time

# Define el token de tu bot de Telegram
TOKEN = '7725298185:AAGgV2fBniVZwQ4GlFUM9OV_Hyb_XaPgn54'
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
    bot.send_message(message.chat.id, "Welcome! Use the buttons below to manage your wallets.", reply_markup=markup)

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
    sol_balance = get_wallet_balance(public_key)

    # Construir mensaje de respuesta
    response_message = (
        f"🔑 *Public Key:* `{public_key}`\n"
        f"💰 *SOL Balance:* {sol_balance:.6f} SOL"
    )

    bot.send_message(message.chat.id, response_message, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data == "confirm_launch")
def confirm_launch(call):
    global user_wallets, user_token_data
    user_id = str(call.from_user.id)
    token_data = user_token_data.get(user_id)
    wallet_info = user_wallets.get(user_id)

    if not wallet_info or not token_data:
        bot.send_message(call.message.chat.id, "❌ Missing wallet or token data. Restart the process.")
        return

    private_key = wallet_info['private_key']
    image_path = None
    try:
        # Descargar la imagen
        image_response = requests.get(token_data['image'], stream=True)
        if image_response.status_code == 200:
            image_path = f"/tmp/{user_id}_token_image.png"
            with open(image_path, 'wb') as f:
                for chunk in image_response.iter_content(1024):
                    f.write(chunk)
        else:
            bot.send_message(call.message.chat.id, "❌ Failed to download the image.")
            return

        # Crear y lanzar el token
        transaction_signature, token_address = send_local_create_tx(
            signer_private_key=private_key,
            token_name=token_data['name'],
            token_symbol=token_data['symbol'],
            description=f"Token {token_data['name']} created via Pump Assistant",
            image_path=image_path,
            twitter_link=token_data['twitter'],
            telegram_link=token_data['telegram'],
            website_link=token_data['website']
        )

        # Guardar la dirección del último token lanzado
        user_token_data[user_id]['last_token_address'] = token_address
        save_data()

        bot.send_message(
            call.message.chat.id,
            f"✅ Token successfully launched!\n\n"
            f"🔗 Transaction: [View on Solscan](https://solscan.io/tx/{transaction_signature})\n"
            f"📃 Token Address: `{token_address}`",
            parse_mode="Markdown"
        )

        # Mostrar el botón para vender los tokens
        markup = types.InlineKeyboardMarkup()
        sell_button = types.InlineKeyboardButton("Sell All Tokens", callback_data=f"sell_token|{token_address}")
        markup.add(sell_button)

        bot.send_message(
            call.message.chat.id,
            "What would you like to do next?",
            reply_markup=markup
        )

    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ An unexpected error occurred: {e}")
    finally:
        if image_path and os.path.exists(image_path):
            os.remove(image_path)

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

    token_data = user_token_data[user_id]
    response_message = (
        f"🤖 You are about to launch a token with the following details:\n\n"
        f"🪙 *Name:* {token_data['name']}\n"
        f"💲 *Symbol:* {token_data['symbol']}\n"
        f"🖼️ *Image:* [View Image]({token_data['image']})\n"
        f"🌐 *Website:* {token_data['website']}\n"
        f"📢 *Telegram:* {token_data['telegram']}\n"
        f"🐦 *Twitter:* {token_data['twitter']}\n\n"
        f"If the information is correct, press Confirm Launch."
    )

    markup = types.InlineKeyboardMarkup()
    confirm_button = types.InlineKeyboardButton("🦾 Confirm Launch", callback_data="confirm_launch")
    markup.add(confirm_button)

    bot.send_message(message.chat.id, response_message, parse_mode="Markdown", reply_markup=markup)

def get_user_token_balance_with_solathon(public_key, token_mint):
    """
    Obtiene el balance de un token específico para el usuario.

    Args:
        public_key (str): Clave pública de la wallet.
        token_mint (str): Dirección del contrato del token SPL.

    Returns:
        float: Cantidad de tokens disponibles.
    """
    try:
        # Validar que las claves sean cadenas válidas
        if not public_key or not isinstance(public_key, str) or len(public_key) != 44:
            raise ValueError("Invalid wallet public key format.")
        if not token_mint or not isinstance(token_mint, str) or len(token_mint) != 44:
            raise ValueError("Invalid token mint format.")

        # Convertir las claves en objetos PublicKey
        public_key_obj = PublicKey(public_key)
        token_mint_obj = PublicKey(token_mint)

        # Obtener cuentas de tokens SPL asociadas a la wallet y al token mint
        response = client.get_token_accounts_by_owner(
            str(public_key_obj),  # Convertir a string
            mint_id=str(token_mint_obj)  # Convertir a string
        )

        # Iterar sobre las cuentas para obtener el balance
        if "value" in response and isinstance(response["value"], list):  # Verifica que "value" sea una lista
            for account in response["value"]:
                account_data = account.get("account", {}).get("data", {}).get("parsed", {}).get("info", {})
                token_amount = account_data.get("tokenAmount", {})
                balance = float(token_amount.get("uiAmount", 0.0))  # Manejar valores inexistentes de forma segura
                if balance > 0:
                    return balance

        # Si no se encuentra balance
        return 0.0
    except ValueError as ve:
        print(f"Error en las claves públicas: {ve}")
        return 0.0
    except Exception as e:
        print(f"Error fetching token balance with Solathon: {e}")
        return 0.0

@bot.callback_query_handler(func=lambda call: call.data.startswith("sell_token"))
def sell_all_tokens(call):
    global user_wallets
    _, token_address = call.data.split("|")
    user_id = str(call.from_user.id)
    wallet_info = user_wallets.get(user_id)

    if not wallet_info:
        bot.send_message(call.message.chat.id, "❌ You do not have a wallet associated. Please restart the process.")
        return

    private_key = wallet_info['private_key']
    try:
        # Realizar la venta utilizando la función sell_token
        transaction_url = sell_token(
            private_key=private_key,
            token_mint=token_address,
            amount=0,  # Vender todo
            denominated_in_sol=False
        )

        if transaction_url.startswith("https://solscan.io/tx/"):
            bot.send_message(
                call.message.chat.id,
                f"✅ Tokens successfully sold!\n\n🔗 Transaction: [View on Solscan]({transaction_url})",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                call.message.chat.id,
                f"❌ Failed to sell tokens. Error: {transaction_url}"
            )
    except Exception as e:
        bot.send_message(call.message.chat.id, f"❌ An error occurred while selling tokens: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "confirm_launch")
def confirm_launch(call):
    global user_wallets, user_token_data, user_states
    user_id = str(call.from_user.id)
    token_data = user_token_data.get(user_id)
    wallet_info = user_wallets.get(user_id)

    if not wallet_info or not token_data:
        bot.send_message(call.message.chat.id, "❌ Missing wallet or token data. Restart the process.")
        return

    private_key = wallet_info['private_key']

    # Descargar la imagen
    image_path = None  
    try:
        image_response = requests.get(token_data['image'], stream=True)
        if image_response.status_code == 200:
            image_path = f"/tmp/{user_id}_token_image.png"
            with open(image_path, 'wb') as f:
                for chunk in image_response.iter_content(1024):
                    f.write(chunk)
        else:
            bot.send_message(call.message.chat.id, "❌ Failed to download the image.")
            return

        transaction_signature, token_address = send_local_create_tx(
            signer_private_key=private_key,
            token_name=token_data['name'],
            token_symbol=token_data['symbol'],
            description=f"Token {token_data['name']} created via Pump Assistant",
            image_path=image_path,
            twitter_link=token_data['twitter'],
            telegram_link=token_data['telegram'],
            website_link=token_data['website']
        )

        bot.send_message(
            call.message.chat.id,
            f"✅ Token successfully launched!\n\n"
            f"🔗 Transaction: [View on Solscan](https://solscan.io/tx/{transaction_signature})\n"
            f"📃 Token Address: `{token_address}`",
            parse_mode="Markdown"
        )

        # Mostrar el menú para vender el token
        markup = types.InlineKeyboardMarkup()
        sell_button = types.InlineKeyboardButton("Sell All Tokens", callback_data=f"sell_token|{token_address}")
        markup.add(sell_button)

        bot.send_message(
            call.message.chat.id,
            "What would you like to do next?",
            reply_markup=markup
        )

    except ValueError as ve:
        # Manejar errores de fondos insuficientes
        if "insufficient lamports" in str(ve):
            bot.send_message(call.message.chat.id, "❌ Insufficient funds. Please ensure at least 0.015 SOL in your wallet.")
        else:
            bot.send_message(call.message.chat.id, f"❌ An error occurred: {ve}")
    except Exception as e:
        # Manejar errores inesperados
        if "insufficient lamports" in str(e):
            bot.send_message(call.message.chat.id, "❌ Insufficient funds. Please ensure at least 0.015 SOL in your wallet.")
        else:
            bot.send_message(call.message.chat.id, f"❌ An unexpected error occurred. Please try again later.")
    finally:
        # Limpiar archivo temporal de la imagen
        if image_path and os.path.exists(image_path):
            os.remove(image_path)

if __name__ == '__main__':
    bot.infinity_polling(timeout=10, long_polling_timeout=5)

