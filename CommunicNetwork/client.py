import os
import random

# Constants
MIN_PACKET_SIZE_BYTES = 1000
MAX_PACKET_SIZE_BYTES = 2000

# Client Side
class QuicClient:
    # Other methods remain unchanged

    def generate_random_data(self, size):
        """Generate random data of the specified size."""
        return os.urandom(size)

    def send_data(self, stream_id):
        """Generate random data within the specified size range and send it over the stream."""
        packet_size = random.randint(MIN_PACKET_SIZE_BYTES, MAX_PACKET_SIZE_BYTES)
        data = self.generate_random_data(packet_size)
        super().send_data(stream_id, data)
