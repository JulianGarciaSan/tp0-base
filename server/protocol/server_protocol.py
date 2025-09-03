import struct
import socket
import logging

from common.utils import Bet, store_bets

class ServerProtocol:
    HEADER_SIZE = 4  # Tamaño del header en bytes (uint32 BigEndian)

    def __init__(self, client_socket):
        self.client_socket = client_socket
        
    def _pack_uint32_be(self, value):
        return value.to_bytes(self.HEADER_SIZE, byteorder='big')

    def _unpack_uint32_be(self, data):
        return int.from_bytes(data, byteorder='big')
    
    def receive_message(self):
        try:
            header_data = self._receive_complete(self.HEADER_SIZE)
            if not header_data:
                return None
            
            message_length = self._unpack_uint32_be(header_data)
            message_data = self._receive_complete(message_length)
            if not message_data:
                return None
                
            return message_data.decode('utf-8')
        except Exception as e:
            logging.error(f"action: receive_message | result: error | error: {e}")
            return None
    
    def send_message(self, message):
        try:
            data = message.encode('utf-8')
            header = self._pack_uint32_be(len(data))
            self._send_complete(header)
            self._send_complete(data)
            return True
        except BrokenPipeError:
            logging.debug(f"action: send_message | result: client_disconnected")
            return False
            
        except OSError as e:
            if e.errno == 32:
                logging.debug(f"action: send_message | result: client_disconnected") 
                return False
            else:
                logging.error(f"action: send_message | result: error | error: {e}")
                raise
    
    def send_response(self, success, error_message=None):
        logging.info(f"action: send_response | result: {'success' if success else 'error'}")
        if success:
            sent = self.send_message("OK")
        else:
            sent = self.send_message(f"ERROR|{error_message or 'Unknown error'}")

        if not sent:
            logging.debug("action: send_response | result: client_gone")
        else:
            logging.info("action: send_response | result: success")
            
        return sent

    def _receive_complete(self, num_bytes):
        buffer = b''
        while len(buffer) < num_bytes:
            chunk = self.client_socket.recv(num_bytes - len(buffer))
            if not chunk:
                return None 
            buffer += chunk
        return buffer
    
    def _send_complete(self, data):
        total_sent = 0
        while total_sent < len(data):
            sent = self.client_socket.send(data[total_sent:])
            if sent == 0:
                raise RuntimeError("Socket connection broken")
            total_sent += sent