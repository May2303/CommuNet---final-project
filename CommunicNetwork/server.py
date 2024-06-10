import struct
import time
import matplotlib.pyplot as plt
import asyncio
import sys
from aioquic.asyncio import QuicConnectionProtocol, serve
from aioquic.asyncio.server import QuicServer
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import HandshakeCompleted, StreamDataReceived
from aioquic.asyncio.protocol import QuicConnectionProtocol
from aioquic.asyncio import connect



class QuicServer(QuicConnectionProtocol):
    local_port = 12345
    local_ip = '127.0.0.1'
    packet_size = 1024
    ready_message = b"READY"  # Message to indicate that the server is ready to receive data (Identify new iteration)
    finished_message = b"FINISHED"  # Message to indicate that the server has received all data
    timeout_duration = 30  # Timeout duration for receiving data from the client
    num_iterations = 10

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.configuration = QuicConfiguration(is_client=False)
        self.configuration.verify_mode = None  # Disable certificate verification
        self.connection = None
        self.stream_data = {}  # Stores data per stream per iteration
        self.total_bytes_received = 0
        self.total_packets_received = 0
        self.start_time = {}  # Contains starting time of each stream per iteration
        self.end_time = {}  # Contains ending time for each stream per iteration
        self.iteration = 0  # Iteration counter
        self.iteration_metrics = []  # To store average metrics for each iteration

    
    # Establish a QUIC connection with the client
    async def setup_connection(self, host, port):
        try:
            # Configure SSL/TLS parameters
            self.configuration.verify_mode = None
            self.configuration.max_data = 2 ** 60
            self.configuration.max_stream_data = 2 ** 60
            self.configuration.load_cert_chain(certfile='cert.pem', keyfile='key.pem')  # Load the SSL certificate and key

            # Establish QUIC connection
            async with connect(host, port, configuration=self.configuration, create_protocol=QuicServer) as connection:
                self.connection = connection

                # Wait until the handshake is complete before proceeding
                await self.connection.wait_handshake_complete()

                # Print a message upon successful connection
                print("QUIC connection established.")
        except Exception as e:
            print(f"Failed to establish QUIC connection: {e}")
            raise ConnectionRefusedError("Failed to establish QUIC connection") from e
    
    # Function to close QUIC connection
    async def close_connection(self):
        if hasattr(self, 'connection') and self.connection is not None:
            await self.connection.close()
            print("QUIC connection closed.")

    # Process the initial message sent by the client
    # Used to extract the number of streams and file size
    async def process_initial_message(self):
        try:
            # Wait for the initial message on the control stream (stream ID 0)
            event = await asyncio.wait_for(self.connection.wait_event(), timeout=10.0)
            
            # Check if the received event is a StreamDataReceived event on the control stream
            if isinstance(event, StreamDataReceived) and event.stream_id == 0:
                # Extract the number of streams and file size from the received data
                if len(event.data) < 8:
                    raise ValueError("Initial message is too short")
                num_streams, file_size = struct.unpack("!II", event.data)
                return num_streams, file_size
        except asyncio.TimeoutError as e: 
            print("Timeout reached while waiting for initial message")
            await self.close_connection()
            raise TimeoutError("Failed to establish QUIC connection") from e


    # Update statistics for the received stream
    def update_statistics(self, received_stream_id, data):
        if self.iteration not in self.stream_data:
            self.stream_data[self.iteration] = {}
        if received_stream_id not in self.stream_data[self.iteration]:
            self.stream_data[self.iteration][received_stream_id] = {"bytes_received": 0, "packets_received": 0}
            self.start_time[(self.iteration, received_stream_id)] = time.perf_counter()
        self.stream_data[self.iteration][received_stream_id]["bytes_received"] += len(data)
        self.stream_data[self.iteration][received_stream_id]["packets_received"] += 1

        self.total_bytes_received += len(data)
        self.total_packets_received += 1

    # Receive packets from the client and collect data
    async def receive_packets(self, num_streams):
        try:
            received_data = {}
            end_streams_received = 0  # Track the number of end-of-stream events received for all streams
            while end_streams_received < num_streams:  # Continue until all streams have sent their end-of-stream events
                event = await self.connection.wait_event()  # Wait for any event on the connection
                if isinstance(event, StreamDataReceived):  # Check if the event is a stream data received event
                    if event.end_stream:  # Check if it's an end-of-stream event
                        end_streams_received += 1  # Increment the count of end-of-stream events received
                        # Update end time for the received stream
                        received_stream_id = event.stream_id
                        self.end_time[(self.iteration, received_stream_id)] = time.perf_counter()
                    received_stream_id = event.stream_id
                    if received_stream_id not in received_data:
                        received_data[received_stream_id] = b""
                    received_data[received_stream_id] += event.data
                    self.update_statistics(received_stream_id, event.data)  # Update statistics for the received stream
            return received_data
        except asyncio.TimeoutError as e:
            print("Timeout reached while waiting for data packets")
            await self.close_connection()
            raise TimeoutError("Failed to receive data packets") from e


    # Send a message to the client to indicate that the server is ready to receive data (Identify new iteration)
    async def send_ready_message(self):
        try:
            # Send the 'READY' message over the control stream (stream ID 0)
            await self.connection.send_stream_data(0, self.ready_message)
            print("Sent 'READY' message to the client.")
        except Exception as e:
            # Handle any errors that occur during sending
            print(f"Failed to send 'READY' message: {e}")
            self.close_connection()
            sys(1)


    # Send a message to the client to indicate that the server has received all data (End of all iterations)
    async def send_finished_message(self):
        try:
            # Send the 'READY' message over the control stream (stream ID 0)
            await self.connection.send_stream_data(0, self.finished_message)
            print("Sent 'READY' message to the client.")
        except Exception as e:
            # Handle any errors that occur during sending
            print(f"Failed to send 'READY' message: {e}")
            self.close_connection()
            sys(1)

    # Calculate metrics for the received data
    def calculate_metrics(self):
        metrics = {}
        for iteration, streams in self.stream_data.items():
            total_iteration_avg_bytes_per_ms = 0
            total_iteration_avg_packets_per_ms = 0
            iteration_metrics = {}
            for stream_id, data in streams.items():
                end_time = self.end_time.get((iteration, stream_id))
                start_time = self.start_time.get((iteration, stream_id))
                if end_time is not None and start_time is not None:
                    elapsed_time_ms = (end_time - start_time) * 1000
                    if elapsed_time_ms == 0:
                        elapsed_time_ms = 1
                    avg_bytes_per_ms = data["bytes_received"] / elapsed_time_ms
                    avg_packets_per_ms = data["packets_received"] / elapsed_time_ms
                    iteration_metrics[stream_id] = {
                        "bytes_transferred": data["bytes_received"],
                        "packets_transferred": data["packets_received"],
                        "average_bytes_per_millisecond": avg_bytes_per_ms,
                        "average_packets_per_millisecond": avg_packets_per_ms,
                    }
                    total_iteration_avg_bytes_per_ms += avg_bytes_per_ms
                    total_iteration_avg_packets_per_ms += avg_packets_per_ms
            metrics[iteration] = iteration_metrics
            iteration_avg_bytes_per_ms = total_iteration_avg_bytes_per_ms / len(streams) if streams else 0
            iteration_avg_packets_per_ms = total_iteration_avg_packets_per_ms / len(streams) if streams else 0
            self.iteration_metrics.append({
                "average_bytes_per_millisecond": iteration_avg_bytes_per_ms,
                "average_packets_per_millisecond": iteration_avg_packets_per_ms,
                "num_streams": len(streams)
            })
        return metrics

    # Print statistics for the received data
    def print_statistics(self, metrics, file_size):
        print(f"\nFile size: {file_size}:")
        for iteration, streams in metrics.items():
            print(f"\nIteration {iteration}:")
            for stream_id, metric in streams.items():
                print(f"\nStream {stream_id}:")
                print(f"Bytes transferred: {metric['bytes_transferred']}")
                print(f"Packets transferred: {metric['packets_transferred']}")
                print(f"Average bytes per millisecond: {metric['average_bytes_per_millisecond']}")
                print(f"Average packets per millisecond: {metric['average_packets_per_millisecond']}")
            avg_metrics = self.iteration_metrics[iteration-1]
            print(f"\nIteration {iteration} Averages:")
            print(f"Average bytes per millisecond: {avg_metrics['average_bytes_per_millisecond']}")
            print(f"Average packets per millisecond: {avg_metrics['average_packets_per_millisecond']}")

    # Plot metrics for the received data
    def plot_metrics(self):
        avg_bytes_per_ms = [metrics["average_bytes_per_millisecond"] for metrics in self.iteration_metrics]
        avg_packets_per_ms = [metrics["average_packets_per_millisecond"] for metrics in self.iteration_metrics]
        num_streams = [metrics["num_streams"] for metrics in self.iteration_metrics]

        plt.figure(figsize=(12, 6))

        plt.subplot(1, 2, 1)
        plt.plot(num_streams, avg_bytes_per_ms, marker='o')
        plt.title('Average Bytes / Millisecond per Iteration vs Number of Streams')
        plt.xlabel('Number of Streams')
        plt.ylabel('Average Bytes / Millisecond per Iteration')
        plt.grid(True)

        plt.subplot(1, 2, 2)
        plt.plot(num_streams, avg_packets_per_ms, marker='o')
        plt.title('Average Packets / Millisecond per Iteration vs Number of Streams')
        plt.xlabel('Number of Streams')
        plt.ylabel('Average Packets / Millisecond per Iteration')
        plt.grid(True)

        plt.tight_layout()
        plt.show()

    async def run(self):
        try:
            await self.setup_connection(self.local_ip, self.local_port)

            for _ in range(self.num_iterations):
                num_streams, file_size = await self.process_initial_message()
                self.iteration += 1
                received_data = await self.receive_packets(num_streams)
                if self.iteration < self.num_iterations:
                    await self.send_ready_message()
                elif self.iteration == self.num_iterations:
                    await self.send_finished_message()
                elif self.iteration > self.num_iterations:
                    print(f"Invalid iteration {self.iteration}")
                    raise ValueError("Invalid iteration number")
        
        # Close the QUIC connection after all iterations are completed
            await self.close_connection()
        
            return file_size

        except Exception as e:
            print(f"An error occurred during the server run: {e}")
            raise
    
# Entry point of the script
async def main():
    quic_protocol = QuicConnectionProtocol(quic=None)
    server = QuicServer(quic=quic_protocol)
    file_size = await server.run()

# Run the main coroutine using asyncio.run()
asyncio.run(main())
