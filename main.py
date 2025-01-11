#!/usr/bin/env python3
"""
This script watches for new RugNinja coins launched on the Algorand blockchain
and buys them.
"""
import time
import sys
import base64
import struct
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from algosdk.v2client import algod
from algosdk import transaction, encoding, mnemonic
from algosdk.atomic_transaction_composer import (
    AtomicTransactionComposer,
    AccountTransactionSigner,
    TransactionWithSigner,
)
from algosdk.abi import Contract
from dotenv import load_dotenv

load_dotenv()  # take environment variables from .env.

with open("RugNinja.arc4.json", encoding="utf-8") as f:
    js = f.read()

c = Contract.from_json(js)

ALGOD_ADDRESS = os.getenv('ALGOD_ADDRESS')
ALGOD_TOKEN = os.getenv('ALGOD_TOKEN')
RUGNINJA_APP_ID = 2020762574
RUGNINJA_ADDRESS = "7TL5PKBGPH4W7LEZW5SW5BGC4TH32XVFV5NVTXE4HTTPVK2JUJODCVTHSU"
WALLET_ADDRESS = os.getenv('WALLET_ADDRESS')
WALLET_MNEMONIC = os.getenv('WALLET_MNEMONIC')
WALLET_PRIVATE_KEY = mnemonic.to_private_key(WALLET_MNEMONIC)
PURCHASE_AMOUNT = int(os.getenv('PURCHASE_AMOUNT'))
WORKERS = int(os.getenv('WORKERS'))

TARGET_APP_ARG = "XrzHXA=="  # base64-encoded argument you want to detect

max_asa_id = 0  # shared variable accessible by both threads
stop_thread = False  # a flag to signal the thread to stop if neede


# Keep track of transaction IDs we've already processed,
# so we don't run buy_coins multiple times for the same transaction.
processed_grpids = set()


def find_created_assets_in_txn(txn_dict):
    """
    Recursively search for asset creation transactions in the given transaction dict.
    """
    created_ids = []
    if "caid" in txn_dict:
        created_ids.append(txn_dict["caid"])

    if "inner-txns" in txn_dict:
        for itxn in txn_dict["inner-txns"]:
            created_ids.extend(find_created_assets_in_txn(itxn))

    if "dt" in txn_dict and "itx" in txn_dict["dt"]:
        for itxn in txn_dict["dt"]["itx"]:
            created_ids.extend(find_created_assets_in_txn(itxn))

    return created_ids


def watch_blocks(algod_client, start_round=None):
    """
    Watch for new blocks and update the global `max_asa_id` variable
    whenever a new asset is created.
    """
    global max_asa_id
    global stop_thread

    # Initialize `current_round` and `max_asa_id` as usual
    status = algod_client.status()
    current_round = (start_round or (status["last-round"] + 1))

    while not stop_thread:
        status = algod_client.status()
        latest_round = status["last-round"]
        if latest_round < current_round:
            time.sleep(1)
            continue

        block_info = algod_client.block_info(current_round)
        block_txns = block_info["block"].get("txns", [])

        updated = False
        for top_level_txn in block_txns:
            created_ids = find_created_assets_in_txn(top_level_txn)
            if not created_ids:
                continue

            local_max = max(created_ids)
            # Update the global shared variable
            if local_max > max_asa_id:
                max_asa_id = local_max
                updated = True

        current_round += 1

    print("[Thread] watch_blocks stopped.")


def decode_asset_name(tx):
    """
    Retrieve the first 'n' field under 'apbx' in the given tx dict
    and decode it from base64 to a human-readable string.
    """
    try:
        apbx_list = tx["txn"].get("apbx", [])
        if not apbx_list:
            return None

        # For this example, we'll decode only the first apbx entry's "n"
        first_apbx = apbx_list[0]
        encoded_name = first_apbx.get("n")
        if not encoded_name:
            return None

        # Decode the base64-encoded name
        decoded_name = base64.b64decode(encoded_name).decode("utf-8")
        return decoded_name
    except Exception as e:
        print(f"Error decoding asset name: {e}")
        return None

def create_box_name(address, value):
    """
    Create a box name by concatenating the first 32 bytes of a 58-byte address
    and an 8-byte uint64 value.
    
    Args:
    address (bytes): The 58-byte address.
    value (int): The uint64 value to append.
    
    Returns:
    bytes: A 40-byte result combining the first 32 bytes of the address and the uint64 value.
    """
    # Ensure the address is at least 32 bytes
    if len(address) < 32:
        raise ValueError("Address must be at least 32 bytes.")

    sender_address_call = encoding.decode_address(address)

    # Use the first 32 bytes of the address
    address_bytes = sender_address_call[:32]

    # Convert the uint64 value to 8 bytes in big-endian order
    value_bytes = struct.pack('>Q', value)
    #print(f"Value bytes: {value_bytes}")

    # Concatenate the address bytes and the uint64 bytes
    result = address_bytes + value_bytes
    return result

def create_tbox_name(address):
    """
    Create a box name by taking the first 32 bytes of the decoded address and 
    prefixing it with the lowercase letter 't'.

    Args:
        address (str): The 58-byte encoded address string.
        value (int): A uint64 value (unused in this updated version).

    Returns:
        bytes: A 33-byte result consisting of 't' followed by the first 
               32 bytes of the decoded address.
    """
    # Decode the address to bytes
    sender_address_call = encoding.decode_address(address)

    # Ensure the decoded address is at least 32 bytes
    if len(sender_address_call) < 32:
        raise ValueError("Decoded address must be at least 32 bytes.")

    # Use the first 32 bytes of the address
    address_bytes = sender_address_call[:32]

    # Prepend 't' to the address bytes (no longer adding value)
    result = b't' + address_bytes

    return result

def buy_token(algod_client, asset_name, asset_id, amount, min_amount_out):
    """
    Buy a token from the RugNinja contract.
    """
    try:
        tx_params = algod_client.suggested_params()
        signer = AccountTransactionSigner(WALLET_PRIVATE_KEY)
        atc = AtomicTransactionComposer()
        try:
            pmt_txn = transaction.PaymentTxn(
                sender=WALLET_ADDRESS,
                receiver=RUGNINJA_ADDRESS,
                amt=amount,
                sp=tx_params
            )

            atc.add_transaction(TransactionWithSigner(txn=pmt_txn, signer=signer))

            app_args = [
                asset_id,
                min_amount_out
            ]

            atc.add_method_call(
                app_id=RUGNINJA_APP_ID,
                method=c.get_method_by_name("buyCoin"),
                sender=WALLET_ADDRESS,
                signer=signer,
                sp=tx_params,
                on_complete=transaction.OnComplete.NoOpOC,
                method_args=app_args,
                foreign_assets=[asset_id],
                boxes=[
                    [RUGNINJA_APP_ID, asset_name.encode('utf-8')],
                    [RUGNINJA_APP_ID, create_tbox_name(WALLET_ADDRESS)],
                    [RUGNINJA_APP_ID, create_box_name(WALLET_ADDRESS, asset_id)]
                ]
            )
        except Exception as e:
            print(f"New Error {asset_id}: {e}")
            return None

        # Execute the transaction. Just fling it out there.
        atc.execute(algod_client, 0)
        return asset_id
    except Exception as e:
        #print(f"Error buying: {e}")
        return None

def buy(algod_client, last_asset_id, buy_asset_name):
    """
    Main function to buy the new coin.
    """
    try:
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            # Submit the function 50 times in parallel
            futures = [executor.submit(buy_token, algod_client, buy_asset_name, last_asset_id+i, PURCHASE_AMOUNT, 1000) for i in range(WORKERS)]
            # Retrieve results once they are completed
            results = [future.result() for future in futures]

        for r in results:
            if r is not None:
                return r
    except Exception as e:
        print(f"Error buy loop: {e}")
        return None
    return None

def check_mempool_for_app_args(algod_client, app_id, app_arg):
    """
    Fetch pending (mempool) transactions from the local Algorand node,
    check if there is an application call to `app_id` that includes
    `app_arg` in its arguments.
    """
    try:
        response = algod_client.pending_transactions()
        top_transactions = response.get("top-transactions", [])

        if not top_transactions:
            print("No transactions currently in mempool.")
            return

        for txn_info in top_transactions:
            txn_fields = txn_info.get("txn", {})

            # We only care about application call transactions (type "appl")
            if txn_fields.get("type") != "appl":
                continue

            # Check if this is the specific app ID
            if txn_fields.get("apid") != app_id:
                continue

            grp_id = txn_fields.get("grp")
            if not grp_id:
                # If for some reason the group ID isn't available, skip
                continue

            # If we have already processed this txn_id, skip
            if grp_id in processed_grpids:
                continue

            # Get the application arguments (base64-encoded strings in a list)
            app_args = txn_fields.get("apaa", [])
            # Check if our target argument is present
            if app_arg in app_args:

                # Mark this grp_id as processed
                processed_grpids.add(grp_id)

                asset_name = decode_asset_name(txn_info)

                token_creator_wallet = txn_fields.get('snd')

                # Call the buy function exactly once for this grp_id
                asset_id = buy(algod_client, max_asa_id, asset_name)

                if asset_id is not None:
                    print("--------------------------------------------------")
                    print("Successfully bought new coin!")
                    print(f"Asset ID: {asset_id}")
                    print(f"Asset Name: {asset_name}")
                    print(f"Creator Address: {token_creator_wallet}")
                    print(f"https://rug.ninja/{asset_name}")
                    print("--------------------------------------------------")
                    continue

    except Exception as e:
        print(f"Error checking mempool: {e}", file=sys.stderr)


if __name__ == "__main__":
    # Create an algod client
    client = algod.AlgodClient(ALGOD_TOKEN, ALGOD_ADDRESS)

    # Create and start the thread
    t = threading.Thread(target=watch_blocks, args=(client,))
    t.start()

    try:
        while True:
            check_mempool_for_app_args(client, RUGNINJA_APP_ID, TARGET_APP_ARG)
            time.sleep(1)

    except KeyboardInterrupt:
        print("[Main] Keyboard interrupt received; stopping thread...")
        stop_thread = True
        t.join()
        print("[Main] Thread has stopped.")
