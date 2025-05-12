import asyncio
import aiohttp
import logging
import os
import time
import platform
import ctypes
from toolscord import Logger, display_banner, ToolsCordColors

# Set Windows terminal title
def set_terminal_title(title):
    if platform.system() == "Windows":
        ctypes.windll.kernel32.SetConsoleTitleW(title)

# Function to clear console
def clear_console():
    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")

# Function to mask token
def mask_token(token):
    if not token or len(token) < 20:
        return token
    
    # Show only first 10 and last 5 characters, mask the rest
    visible_part_start = token[:10]
    visible_part_end = token[-5:]
    masked_part = "*" * 10
    
    return f"{visible_part_start}..."

# Configure logger
logger = Logger()

class TokenChecker:
    def __init__(self):
        self.tokens = []
        self.valid_tokens = []
        self.invalid_tokens = []
        self.locked_tokens = []
        self.tokens_with_payment = []
        
    def load_tokens(self, file_path="tokens.txt"):
        """Load tokens from file in email:pass:token format or plain token format"""
        try:
            with open(file_path, 'r') as file:
                for line in file:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                        
                    if ':' in line:
                        # Email:Pass:Token format
                        try:
                            parts = line.split(':')
                            if len(parts) >= 3:
                                token = parts[2]
                                self.tokens.append(token)
                        except:
                            pass
                    else:
                        # Plain token format
                        self.tokens.append(line)
                        
            logger.info(f"Loaded {len(self.tokens)} tokens")
        except FileNotFoundError:
            logger.error(f"File {file_path} not found. Please create it with tokens in email:pass:token format or plain token format.")
            exit(1)
    
    def headers(self, token):
        """Create headers for Discord API requests"""
        return {
            "Authorization": token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
    
    async def check_token(self, token):
        """Check if a token is valid, locked, or invalid"""
        try:
            async with aiohttp.ClientSession() as client:
                async with client.get(
                    "https://discord.com/api/v9/users/@me",
                    headers=self.headers(token)
                ) as response:
                    if response.status == 200:
                        user_json = await response.json()
                        username = user_json.get('username')
                        discriminator = user_json.get('discriminator')
                        user_id = user_json.get('id')
                        full_username = f"{username}#{discriminator}" if discriminator != '0' else username
                        #logger.success(f"Valid token: {full_username} ({user_id}) | {mask_token(token)}")
                        self.valid_tokens.append(token)
                        await self.payment_sources(token)
                    elif response.status == 401:
                        logger.error(f"Invalid token: {mask_token(token)}")
                        self.invalid_tokens.append(token)
                    elif response.status == 403:
                        logger.warning(f"Locked token: {mask_token(token)}")
                        self.locked_tokens.append(token)
                    else:
                        logger.error(f"Unknown status ({response.status}): {mask_token(token)}")
                        self.invalid_tokens.append(token)
        except Exception as e:
            logger.error(f"Error checking token {mask_token(token[:30])}: {str(e)}")
            await asyncio.sleep(2)
            await self.check_token(token)
    
    async def payment_sources(self, token):
        """Check payment sources for a token"""
        try:
            async with aiohttp.ClientSession(headers=self.headers(token)) as client:
                async with client.get(
                    "https://discord.com/api/v9/users/@me/billing/payment-sources"
                ) as response:
                    if response.status != 200:
                        logger.error(f"Failed to check payment sources: {mask_token(token)}")
                        return
                    
                    json = await response.json()
                    if json != []:
                        valid_sources = [source for source in json if source["invalid"] is False]
                        valid_count = len(valid_sources)
                        
                        if valid_count > 0:
                            self.tokens_with_payment.append(token)
                            
                            # Identify payment method types
                            payment_types = []
                            for source in valid_sources:
                                if source["type"] == 1:  # Credit Card
                                    payment_types.append("CC")
                                elif source["type"] == 2:  # PayPal
                                    payment_types.append("PP")
                                else:
                                    payment_types.append(f"Type-{source['type']}")
                            
                            payment_methods_str = ", ".join(payment_types)
                            logger.success(f"{valid_count} Valid Payment method(s) [{payment_methods_str}] ({mask_token(token)})")
                        else:
                            logger.warning(f"Has payment sources but all invalid ({mask_token(token)})")
                    else:
                        logger.error(f"No payment sources ({mask_token(token)})")
        except Exception as e:
            logger.error(f"Error checking payment sources for {mask_token(token[:30])}: {str(e)}")
            await asyncio.sleep(2)
            await self.payment_sources(token)
    
    async def check_all_tokens(self):
        """Check all loaded tokens"""
        tasks = []
        for token in self.tokens:
            tasks.append(self.check_token(token))
        await asyncio.gather(*tasks)
    
    def save_results(self):
        """Save results to files"""
        os.makedirs("results", exist_ok=True)
        
        with open("results/valid_tokens.txt", "w") as f:
            for token in self.valid_tokens:
                f.write(f"{token}\n")
        
        with open("results/invalid_tokens.txt", "w") as f:
            for token in self.invalid_tokens:
                f.write(f"{token}\n")
        
        with open("results/locked_tokens.txt", "w") as f:
            for token in self.locked_tokens:
                f.write(f"{token}\n")
        
        with open("results/tokens_with_payment.txt", "w") as f:
            for token in self.tokens_with_payment:
                f.write(f"{token}\n")
        
        logger.info(f"Results saved to 'results' folder")
    
    def print_summary(self):
        """Print summary of results"""
        print("\n" + "="*50)
        logger.log("SUMMARY:", color=ToolsCordColors.CYAN, bold=True)
        logger.success(f"Valid tokens: {len(self.valid_tokens)}")
        logger.error(f"Invalid tokens: {len(self.invalid_tokens)}")
        logger.warning(f"Locked tokens: {len(self.locked_tokens)}")
        logger.success(f"Tokens with payment: {len(self.tokens_with_payment)}")
        print("="*50)


async def main():
    clear_console()
    set_terminal_title("ToolsCord Payment Checker")
    display_banner()
    print("="*50)
    
    checker = TokenChecker()
    checker.load_tokens()
    
    if not checker.tokens:
        logger.error("No tokens loaded. Exiting...")
        return
    
    logger.info(f"Starting to check {len(checker.tokens)} tokens...")
    await checker.check_all_tokens()
    
    checker.save_results()
    checker.print_summary()
    
    logger.log("Process completed!", color=ToolsCordColors.CYAN, bold=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.error("Process interrupted by user.")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")
