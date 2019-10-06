# clhwi: C-Lightning Plugin to Fund Channels Directly from Hardware Wallets

### Setup

Install `hwi` and `python-bitcoinrpc` to your _global python 3 installation_

```
python3 -m pip install hwi python-bitcoinrpc
```

If you're on Linux, you may need to install hardware wallet udev rules (probably requires `sudo`):

```
hwi installudevrules
```

Make sure you have `server=1` in your `bitcoin.conf`. Run bitcoin core in testnet mode:

```
bitcoind -testnet
```

Add the following values to your `~/.lightning/config`:

```
network=testnet
bitcoin-rpcuser=<your-bitcoin-rpc-username>
bitcoin-rpcpassword=<your-bitcoin-rpc-password>
bitcoin-rpcport=<your-bitcoin-rpc-testnet-port>
bitcoin-rpcconnect=<your-bitoin-rpc-testnet-host>
```

Run lightnind in testnet mode with the plugin specified:

```
/lightningd --network=testnet --plugin=/path/to/clhwi.py
```

### Usage

Plug in device and unlock hardware device.

Run the following command to create a watch-only Bitcoin Core wallet associated with your device. `WALLETNAME` will be the name of the watch-only wallet within Bitcoin Core:

```
$ lightning-cli hwi-initialize WALLETNAME
"fund this address: 2N1cGNNAv4hMRhoCsT3TK3LH7Ltfceyu2kx"
```

[Fund the address returned above](https://testnet-faucet.mempool.co/)

Locate a node to open a channel with ([1ml](https://1ml.com/testnet) can help here). Grabe the node id (pubkey@host:port). 

For example, to open a 100,000 sat channel with [this node](https://1ml.com/testnet/node/0303ba0fed62039df562a77bfcec887a9aa0767ff6519f6e2baa1309210544cd3d), run the following

```
$ lightning-cli hwi-open-channel 100000 0303ba0fed62039df562a77bfcec887a9aa0767ff6519f6e2baa1309210544cd3d@5.9.150.112:9735 WALLETNAME
``

Confirm the transaction on your device and the channel should open.

### TODO:

- This proof-of-concept makes many unnecessary assumptions (required config values, Bitcoin Core backend). Perhaps it would be better to just offer a `sign-funding-tx` method that takes a PSBT as argument -- you can produce this PSBT any way you like, instead of using bitcoin RPC within the plugin.
- Remove `python-bitcoinrpc` dependency
