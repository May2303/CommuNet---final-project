import struct
import random

class QuicPacket:
    # Constants for packet types
    PACKET_TYPE_INITIAL = 0x00
    PACKET_TYPE_RETRY = 0x01
    PACKET_TYPE_HANDSHAKE = 0x02
    PACKET_TYPE_1RTT = 0x03

    # Constructor
    def __init__(self, packet_type: int, packet_number: int, payload: bytes):
        """
        Initialize a QUIC packet with the given type, number, and payload.

        Args:
            packet_type (int): The type of the QUIC packet.
            packet_number (int): The packet number of the QUIC packet.
            payload (bytes): The payload of the QUIC packet.
        """
        self.packet_type = packet_type
        self.packet_number = packet_number
        self.payload = payload

    # Method to encode the QUIC packet header
    def encode_header(self) -> bytes:
        """
        Encode the QUIC packet header.

        Returns:
            bytes: Encoded QUIC packet header.
        """
        # Format string "!B I" specifies the format of the packet header.
        # "!": Specifies network (big-endian) byte order.
        # "B": Specifies an unsigned byte (1 byte) for the packet type.
        # "I": Specifies an unsigned integer (4 bytes) for the packet number.
        header = struct.pack("!B I", self.packet_type, self.packet_number)
        return header

    # Method to decode the QUIC packet header
    @staticmethod
    def decode_header(encoded_header: bytes) -> tuple:
        """
        Decode the QUIC packet header.

        Args:
            encoded_header (bytes): Encoded QUIC packet header.

        Returns:
            tuple: Decoded packet type and packet number.
        """
        # Format string "!B I" specifies the format of the packet header.
        # "!": Specifies network (big-endian) byte order.
        # "B": Specifies an unsigned byte (1 byte) for the packet type.
        # "I": Specifies an unsigned integer (4 bytes) for the packet number.
        packet_type, packet_number = struct.unpack("!B I", encoded_header)
        return packet_type, packet_number
