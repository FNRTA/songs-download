from Crypto.Hash import MD5
from Crypto.Cipher import Blowfish
from binascii import a2b_hex, b2a_hex
import struct


class DeezerCrypto:
    @staticmethod
    def md5hex(data: bytes) -> bytes:
        h = MD5.new()
        h.update(data)
        return b2a_hex(h.digest())

    @staticmethod
    def calc_blowfish_key(song_id: str) -> str:
        key = b"g4el58wc0zvf9na1"
        songid_md5 = DeezerCrypto.md5hex(song_id.encode())
        xor_op = lambda i: chr(songid_md5[i] ^ songid_md5[i + 16] ^ key[i])
        return "".join([xor_op(i) for i in range(16)])

    @staticmethod
    def decrypt_chunk(data: bytes, key: str) -> bytes:
        iv = a2b_hex("0001020304050607")
        cipher = Blowfish.new(key.encode(), Blowfish.MODE_CBC, iv)
        return cipher.decrypt(data)

    @staticmethod
    def decrypt_file(file_handle, key: str, output_handle):
        block_size = 2048
        block_index = 0

        for data in file_handle.iter_content(block_size):
            if not data:
                break

            is_encrypted = ((block_index % 3) == 0)
            is_whole_block = len(data) == block_size

            if is_encrypted and is_whole_block:
                data = DeezerCrypto.decrypt_chunk(data, key)

            output_handle.write(data)
            block_index += 1
