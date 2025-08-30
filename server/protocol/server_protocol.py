import struct
import socket
import logging

from common.utils import Bet, store_bets

class ServerProtocol:
   def __init__(self, client_socket):
       self.client_socket = client_socket
   
   def receive_message(self):
       """Recibe un mensaje completo leyendo primero la longitud"""
       header_data = self._receive_complete(4)
       if not header_data:
           return None
       
       message_length = struct.unpack('!I', header_data)[0]
       
       message_data = self._receive_complete(message_length)
       if not message_data:
           return None
           
       return message_data.decode('utf-8')
   
   def send_message(self, message):
       """Envía un mensaje con longitud al principio"""
       data = message.encode('utf-8')
       
       header = struct.pack('!I', len(data))
       
       self._send_complete(header)
       self._send_complete(data)
   
   def _receive_complete(self, num_bytes):
       """Recepción completa para evitar short-read"""
       buffer = b''
       while len(buffer) < num_bytes:
           chunk = self.client_socket.recv(num_bytes - len(buffer))
           if not chunk:
               return None 
           buffer += chunk
       return buffer
   
   def _send_complete(self, data):
       """Envío completo para evitar short-write"""
       total_sent = 0
       while total_sent < len(data):
           sent = self.client_socket.send(data[total_sent:])
           if sent == 0:
               raise RuntimeError("Socket connection broken")
           total_sent += sent
   
   def parse_bet(self, message):
       """Parsea un mensaje de apuesta con formato: APUESTA|agency|first_name|last_name|document|birthdate|number"""
       try:
           parts = message.split('|')
           logging.error(f"DEBUG: Received message: {message}")
           logging.error(f"DEBUG: Parts count: {len(parts)}, Parts: {parts}")

           if len(parts) != 7 or parts[0] != 'APUESTA':
               logging.error(f"action: parse_bet | result: error | error: invalid_format | parts: {len(parts)}")
               return None
           
           _, agency, first_name, last_name, document, birthdate, number = parts
           
           bet = Bet(agency, first_name, last_name, document, birthdate, number)
           return bet
       
       except ValueError as e:
           logging.error(f"action: parse_bet | result: error | error: invalid_data | detail: {e}")
           return None
       except Exception as e:
           logging.error(f"action: parse_bet | result: error | error: {e}")
           return None
   
   def send_response(self, success, error_message=None):
       """Envía respuesta al cliente"""
       if success:
           self.send_message("OK")
       else:
           self.send_message(f"ERROR|{error_message or 'Unknown error'}")
   
   def handle_bet_request(self):
       """Maneja una solicitud de apuesta completa"""
       try:
           # Recibir mensaje
           message = self.receive_message()
           if not message:
               logging.error("action: receive_message | result: error | error: no_message_received")
               return False
           
           logging.debug(f"action: receive_message | result: success | message: {message}")
           
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