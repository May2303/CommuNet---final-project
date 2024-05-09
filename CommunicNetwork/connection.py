import socket

class QUICConection:
# Your QUICConection class implementation here...

# Create a QUICConection instance
connection = QUICConection()

# Create a UDP socket
udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Bind the socket to a specific address and port
udp_socket.bind(('0.0.0.0', 12345))  # Example address and port

# Connect the socket to the server's address and port
udp_socket.connect(('example.com', 54321))  # Example server address and port
