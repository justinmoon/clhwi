#!/usr/bin/env python3
"""
- fundchannel_start
    - address
- 
"""
from decimal import Decimal
from lightning import Plugin, LightningRpc
from bitcoinrpc.authproxy import AuthServiceProxy
from hwilib import commands, serializations
import time
from pathlib import Path

plugin = Plugin()

lightning_rpc = None
bitcoin_rpc = None
wallet_rpc = None
rpc_settings = {}

template = "http://{user}:{password}@{host}:{port}/wallet/{wallet_name}"


COIN_PER_SAT = Decimal(10) ** -8
SAT_PER_COIN = 100_000_000

def btc_to_sat(btc):
    return int(btc*SAT_PER_COIN)

def sat_to_btc(sat):
    return Decimal(sat/100_000_000).quantize(COIN_PER_SAT)

def get_device_and_client():
    devices = commands.enumerate()
    if len(devices) < 1:
        raise Exception('No hardware wallets detected')
    if len(devices) > 1:
        raise Exception('You can only have 1 device plugged in at a time')
    device = devices[0]
    if 'fingerprint' not in device:
        raise Exception('Device is locked')
    client = commands.get_client(device['type'], device['path'])
    client.is_testnet = True
    return device, client

@plugin.method("hwi-initialize")
def hwi_initialize(plugin, bitcoin_wallet_name):
    # create Core watch-only wallet
    bitcoin_rpc.createwallet(bitcoin_wallet_name, True)
    # importmulti
    device, client = get_device_and_client()
    keypool = commands.getkeypool(client, None, 0, 100, keypool=True)

    # construct rpc for this wallet
    rpc_settings['wallet_name'] = bitcoin_wallet_name
    uri = template.format(**rpc_settings)
    wallet_rpc = AuthServiceProxy(uri)

    # import keys
    r = wallet_rpc.importmulti(keypool)
    plugin.log(str(r))
    
    address = wallet_rpc.getnewaddress()
    # return {'result': 'fund this address: ' + address}
    return 'fund this address: ' + address

@plugin.method("hwi-open-channel")
def hwi_open_channel(plugin, amount, node_id, bitcoin_wallet_name):
    """
    hi
    """
    # fixme: return json
    assert '@' in node_id, "node_id should be pubkey@host:port"

    # load watch-only wallet
    wallets = bitcoin_rpc.listwallets()
    if bitcoin_wallet_name not in wallets:
        rpc.loadwallet(bitcoin_wallet_name)
    plugin.log('loaded watch-only wallet')

    # start channel funding
    lightning_rpc.connect(node_id)
    node_pubkey = node_id.split('@')[0]
    address = lightning_rpc.fundchannel_start(node_pubkey, amount)['funding_address']
    plugin.log('started channel open')

    try:
        # construct rpc for this wallet
        rpc_settings['wallet_name'] = bitcoin_wallet_name
        uri = template.format(**rpc_settings)
        wallet_rpc = AuthServiceProxy(uri)

        # create transaction
        raw_unsigned_psbt = wallet_rpc.walletcreatefundedpsbt(
            # let Bitcoin Core choose inputs
            [],
            # Outputs
            [{address: str(sat_to_btc(amount))}],
            # Locktime
            0,
            {
                # Include watch-only outputs
                "includeWatching": True,
            },
            # Include BIP32 derivation paths in the PSBT
            True,
        )['psbt']
        unsigned_psbt = serializations.PSBT()
        plugin.log('confirm on your device')
        unsigned_psbt.deserialize(raw_unsigned_psbt)
        plugin.log('created psbt')

        # sign transaction
        device, client = get_device_and_client()
        raw_signed_psbt = client.sign_tx(unsigned_psbt)['psbt']
        signed_psbt = serializations.PSBT()
        signed_psbt.deserialize(raw_signed_psbt)
        plugin.log('signed psbt')
        plugin.log(raw_signed_psbt)

        # find index
        vout = -1
        for i, output in enumerate(signed_psbt.outputs):
            if output.hd_keypaths == {}:
                vout = i
                break
        assert vout != -1

        # get txid
        signed_psbt.tx.rehash()
        txid = signed_psbt.tx.hash

        # finalize lightning channel
        r = lightning_rpc.fundchannel_complete(node_pubkey, txid, vout)
        plugin.log(f'channel funding complete: txid={txid} vout={vout}')
        plugin.log(str(r))

        # broadcast
        tx_hex = wallet_rpc.finalizepsbt(raw_signed_psbt)["hex"]
        txid = wallet_rpc.sendrawtransaction(tx_hex)
        plugin.log('broadcasted tx: ' + txid)

    # FIXME: exceptions might not be raised ...
    except Exception as e:
        plugin.log('RPC ERROR: ' + str(e))
        r = lightning_rpc.fundchannel_cancel(node_pubkey)
        plugin.log(str(r))

@plugin.init()
def init(options, configuration, plugin, **kwargs):
    global lightning_rpc, bitcoin_rpc, rpc_settings
    print(configuration)
    # setup lightning rpc
    lightning_dir, rpc_file = configuration['lightning-dir'], configuration['rpc-file']
    path = Path(f"{lightning_dir}/{rpc_file}")
    lightning_rpc = LightningRpc(str(path))

    # setup bitcoin rpc
    config = lightning_rpc.listconfigs()
    rpc_settings['user'] = config['bitcoin-rpcuser']
    rpc_settings['password'] = config['bitcoin-rpcpassword']
    rpc_settings['port'] = config['bitcoin-rpcport']
    rpc_settings['host'] = config['bitcoin-rpcconnect']
    network = config['network']

    template = "http://{user}:{password}@{host}:{port}"
    uri = template.format(**rpc_settings)
    bitcoin_rpc = AuthServiceProxy(uri)

    # check that it works
    bitcoin_rpc.getblockchaininfo()

plugin.run()
