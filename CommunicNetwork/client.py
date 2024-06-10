import os
import socket
import struct
import math
import random
import sys
import time
import asyncio
from aioquic.asyncio import connect
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.quic.events import HandshakeCompleted, StreamDataReceived
from aioquic.quic.configuration import QuicConfiguration

LOCAL_IP = '127.0.0.1'
LOCAL_PORT = 12345
PACKET_SIZE = 1024
READY_MESSAGE = b"READY" # Message sent by the server to indicate that it is ready for the next run (Identify new iteration)
FINISHED_MESSAGE = b"FINISHED" # Message sent by the server to indicate that it has finished all iterations
NUM_ITERATIONS = 10

class QuicClient:
    
    # Initialize the client 
    def __init__(self):
        self.connection = None
        self.streams = []
        self.iteration = 0
        
    # Function to set up QUIC connection
    async def setup_connection(self, host, port):
        try:
            # Configure QUIC connection
            configuration = QuicConfiguration(is_client=True)
            configuration.verify_mode = None  # Disable certificate verification (for testing purposes)

            # Connect to the server
            async with connect(host, port, configuration=configuration, create_protocol=QuicConnectionProtocol) as connection:
                self.connection = connection


            # Print a message upon successful connection
            print("QUIC connection established.")
        except Exception as e:
            # Handle connection errors
            print(f"Failed to establish QUIC connection: {e}")
            # Raise a custom exception
            raise ConnectionRefusedError("Failed to establish QUIC connection") from e
        

    # Function to close QUIC connection
    async def close_connection(self):
        if hasattr(self, 'connection') and self.connection is not None:
            await self.connection.close()
            print("QUIC connection closed.")
            
            
    # Generate random data of a given size
    def generate_random_data(self, size):
        return os.urandom(size)

    
    # Generate a random file of a given size
    def generate_random_file(self, file_size, filename="random_file.txt"):
        with open(filename, "wb") as file:
            file.write(self.generate_random_data(file_size))


    # Create a ID for streams
    async def create_streams(self, num_streams):
        # Open QUIC streams
        for _ in range(num_streams):
            stream = self.connection._quic.create_stream()
            self.streams.append(stream)



    
    async def send_file_over_streams(self, file_size, filename="random_file.txt"):
        # Open the file for reading in binary mode
        with open(filename, "rb") as file:
            # Read the entire file into memory
            file_data = file.read()

            # Calculate the number of packets needed to send the file
            num_packets = math.ceil(file_size / PACKET_SIZE)

            # Iterate over each packet
            for i in range(num_packets):
                # Iterate over each stream and send a chunk of data
                for stream_id in self.streams:
                    start = i * PACKET_SIZE
                    end = min(start + PACKET_SIZE, file_size)
                    chunk = file_data[start:end]
                    
                    # Send the chunk of data over the stream
                    await self.connection.send_stream_data(stream_id, chunk)
                    
                    # Introduce a small delay to prevent overloading the streams
                    await asyncio.sleep(0.0005)

            # After sending all packets, send an end-of-stream message for each stream
            for stream_id in self.streams:
                # Send an empty data frame with the end_stream parameter set to True
                # Automatically closes the stream after sending the data
                await self.connection.send_stream_data(stream_id, b"", end_stream=True)
            # Clean up streams list
            self.streams = []


    # Send the initial message to the server (containing the number of streams and file size)
    # This message is sent over the control stream (stream ID 0)
    async def send_initial_message(self, num_streams, file_size):
        # Pack the number of streams and file size into bytes
        data = struct.pack("!II", num_streams, file_size)
        
        # Send the data over the QUIC connection
        await self.connection.send_stream_data(0, data)




    # Wait for the server to send a 'Ready' message (identifying the next iteration)
    async def wait_for_ready_message(self, timeout=10.0):
        try:
            # Wait for the 'Ready' message over the control stream with a timeout
            event = await asyncio.wait_for(self.connection.wait_event(), timeout)
            
            # Check if the received event is a StreamDataReceived event on the control stream
            if isinstance(event, StreamDataReceived) and event.stream_id == 0:
                if event.data == READY_MESSAGE:
                    print("Received 'Ready for next run' message from server.\n")
                    self.iteration += 1
        except asyncio.TimeoutError:
            # Handle timeout
            print("Timeout waiting for 'Ready for next run' message.")
            self.close_connection()
            os.remove("random_file.txt")
            sys.exit(1)


                
    
    # Wait for the server to send a 'Finished' message (indicating that all iterations are done)
    async def wait_for_finished_message(self, timeout=20.0):
        try:
            # Wait for the 'Finished' message over the control stream with a timeout
            event = await asyncio.wait_for(self.connection.wait_event(), timeout)
            
            # Check if the received event is a StreamDataReceived event on the control stream
            if isinstance(event, StreamDataReceived) and event.stream_id == 0:
                if event.data == FINISHED_MESSAGE:
                    print("Received 'Finished' message from server.\n")
                    self.iteration += 1
        except asyncio.TimeoutError:
            # Handle timeout
            print("Timeout waiting for 'Finished' message.")
            self.close_connection()
            os.remove("random_file.txt")
            sys.exit(1)



    # Run the client
    async def run(self):
        try:
            # Clean up any existing random file
            if os.path.exists("random_file.txt"):
                os.remove("random_file.txt")

            # Set up QUIC connection
            await self.setup_connection(LOCAL_IP, LOCAL_PORT)
            
            # Generate a random file of size between 1MB and 2MB
            file_size = random.randint(1 * 1024 * 1024, 2 * 1024 * 1024)
            self.generate_random_file(file_size)
            print(f"Sending a file of size {file_size} bytes.\n")

            # Iterate for the specified number of iterations
            while self.iteration < NUM_ITERATIONS:
                # Determine the number of streams for the current iteration
                num_streams = self.iteration + 1

                # Create the specified number of streams
                await self.create_streams(num_streams)
                print(f"Iteration {self.iteration + 1}:\n")
                print(f"Sending file over {num_streams} streams.\n")

                # Send the initial message containing the number of streams and file size
                await self.send_initial_message(num_streams, file_size)
                await asyncio.sleep(0.5)

                # Send the file over the created streams
                await self.send_file_over_streams(file_size)

                # Wait for the 'Ready' message from the server for the next iteration
                if self.iteration < NUM_ITERATIONS - 1:
                    await self.wait_for_ready_message()
                # Wait for the 'Finished' message from the server for the last iteration
                elif self.iteration == NUM_ITERATIONS - 1:
                    await self.wait_for_finished_message()
                elif self.iteration > NUM_ITERATIONS - 1:
                    print(f"Invalid iteration {self.iteration}")
                    raise ValueError(f"Invalid iteration: {self.iteration}")
                    
        finally:
            # Close the QUIC connection and perform cleanup
            await self.close_connection()
            if os.path.exists("random_file.txt"):
                os.remove("random_file.txt")
            

async def main():
    quic_protocol = QuicConnectionProtocol(quic=None)
    client = QuicClient()
    await client.run()

# Run the main coroutine using asyncio.run()
asyncio.run(main())
