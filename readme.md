---
title: Getting Started
hide_breadcrumbs: true
---
import Callout from "@/components/Callout.astro";

**_Pump Agent Assistant_**  is a Telegram bot designed to facilitate the creation, management, and trading of Solana-based tokens using the Pump Portal API. The bot allows users to: 

- Create new Solana tokens with custom metadata.
- Buy and sell tokens using an easy-to-use interface.
- Manage their wallets securely.

## Features
- **Wallet Management:**
  - Create a new Solana wallet.
  - Import an existing Solana wallet.
  - View wallet balance.

- **Token Creation:**
  - Launch a new token with customized details.
  - Specify an initial purchase amount.
  - Upload custom token images.

- **Token Trading:**
  - Buy tokens by specifying the amount and slippage.
  - Sell tokens with multiple percentage options (50%, 75%, 100%).


## Commands

#### `/start`
Starts the bot and presents wallet management options.

#### `/wallet`
Displays the current wallet's public key and SOL balance.

#### `/launch`
Initiates the token creation process by requesting the following inputs:
1. Token name
2. Token symbol
3. Image URL
4. Website URL
5. Telegram link
6. Twitter link
7. Initial purchase amount

Upon confirmation, the bot launches the token and provides transaction details.

#### `/buy`
Prompts the user to enter the token mint address, purchase amount, and other necessary details for buying tokens.

#### `/sell`
Prompts the user to enter the token mint address and initiate the selling process.

## Bot Workflow
1. **Wallet Creation or Import:** Users must first create or import a wallet to interact with the bot.
2. **Token Launch:**
   - User provides token details.
   - The bot uploads metadata to IPFS.
   - The bot interacts with the Pump Portal API to create the token.
3. **Token Trading:**
   - Users can buy and sell tokens with preset percentage options.

## Error Handling
Common error messages and solutions:

- `❌ Missing wallet or token data.` - Ensure you have created or imported a wallet and provided the required token details.
- `❌ Insufficient funds.` - Check if you have enough SOL to cover transaction fees.
- `❌ Invalid token address.` - Verify the token mint address before attempting any action.


## Contact
For support or questions, contact [support@pumpassistant.com](mailto:support@pumpassistant.com).




## Next Steps

- **Configure:** Learn about common options in ["Guides"](/guides).
