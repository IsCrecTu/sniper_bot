# sniper_bot
A sniper bot that watches for new coins launched on RugNinja and buys as quick as possible. It does not have any sell code, so that will be up to you.

PLEASE NOTE: NO SUPPORT WILL BE GIVEN IN THE USE OF THIS SCRIPT. If you do not know python or what you are doing, then please do not proceed.

1. Setup your own Algorand node. See https://nodekit.run/ or https://algorand.co/run-a-node.
2. Get that node synced.
3. Shut the Algorand node down.
4. Open the config.json file in the algorand node directory (ubuntu is usually /var/lib/algorand). If you don't have a config.json, rename the config.json.example.
5. Change 'ForceFetchTransactions: false' to 'ForceFetchTransactions: true' 
6. Start the Algorand node up.
7. Create a virtualenv for python (ubuntu command: 'python3 -m venv venv')
8. Activate it depending on OS (ubuntu command: 'source venv/bin/activate')
9. Run 'pip install -r requirements.txt' (You can also just run 'pip install py-algorand-sdk python-dotenv')
10. Rename the .env.example file to .env
11. Open the .env file and update the following:
   
     ALGOD_TOKEN is the Algorand node token found in the algod.token file where you modified the config.json file.
    
     WALLET_ADDRESS - create a hot wallet for this and fund it with a tiny amount.
   
     WALLET_MNEMONIC - put the hot wallet passphrase here.
   
     PURCHASE_AMOUNT - default is set to 1 Algo (1000000). I suggest you start with that and adjust to your risk tolerence.
   
     WORKERS - This is how many threads will be spun up when attempting to buy using a brute force method of figuring out what the ASA ID will be.
12. Run the script (ubuntu command: 'python3 main.py')
13. There will be nothing displayed until it detects and has bought a coin
