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
            logging.error(f"action: receive_message | result: error | error: {e} | thread: {self.thread_id}")
            return None
    
    def send_message(self, message):
        try:
            data = message.encode('utf-8')
            header = self._pack_uint32_be(len(data))
            self._send_complete(header)
            self._send_complete(data)
        except Exception as e:
            logging.error(f"action: send_message | result: error | error: {e} | thread: {self.thread_id}")
            raise
    
    def send_response(self, success, error_message=None):
        """Envía respuesta al cliente"""
        if success:
            self.send_message("OK")
        else:
            self.send_message(f"ERROR|{error_message or 'Unknown error'}")
    
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
            
    def handle_client_request(self):
        try:
            message = self.receive_message()
            if not message:
                return False
            
            if message.startswith('BET|'):
                return self.handle_bet_request(message)
            else:
                self.send_response(False, "Unknown message type")
                return False
                
        except Exception as e:
            logging.error(f"action: handle_client_request | result: error | error: {e} | thread: {self.thread_id}")
            return False
        
    def handle_bet_request(self):
        """Maneja una solicitud de apuesta completa"""
        try:
            message = self.receive_message()
            if not message:
                return False
                        
            bet = self.parse_bet(message)
            if not bet:
                self.send_response(False, "Invalid bet format")
                return False

            store_bets([bet])

            logging.info(f"action: apuesta_almacenada | result: success | dni: {bet.document} | numero: {bet.number}")

            self.send_response(True)
            return True
            
        except Exception as e:
            logging.error(f"action: handle_bet_request | result: error | error: {e}")
            try:
                self.send_response(False, str(e))
            except:
                pass  
            return False

    def parse_bet(self, message):
        """Parsea un mensaje de apuesta con formato: APUESTA|agency|first_name|last_name|document|birthdate|number"""
        
        parts = message.split('|')
        if len(parts) != 7 or parts[0] != 'APUESTA':
            logging.error(f"action: parse_bet | result: error | error: invalid_format | parts: {len(parts)}")
            return None
        
        _, agency, first_name, last_name, document, birthdate, number = parts
        
        bet = Bet(agency, first_name, last_name, document, birthdate, number)
        return bet