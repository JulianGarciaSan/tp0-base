import struct
import socket
import logging

from common.utils import Bet, store_bets

from common.server_state import server_state

class ServerProtocol:
    clients_waiting_winners = {} 

    def __init__(self, client_socket):
        self.client_socket = client_socket
        self.state = server_state
        
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

    def handle_client_request(self):
        """Punto de entrada principal - router de mensajes"""
        try:
            message = self.receive_message()
            if not message:
                return False          
            if message.startswith('BATCH|'):
                return self.handle_batch_request(message)
            elif message.startswith('FINISHED|'):
                return self.handle_finished_notification(message)
            elif message.startswith('QUERY_WINNERS|'):
                return self.handle_winners_query(message)
            else:
                self.send_response(False, "Unknown message type")
                return False
                
        except Exception as e:
            logging.error(f"action: handle_client_request | result: error | error: {e}")
            return False

    def handle_batch_request(self, message):
        """Maneja un batch de apuestas"""
        try:
            bets, error = self.parse_batch(message)
            if error:
                self.send_response(False, error)
                logging.info(f"action: apuesta_recibida | result: fail | cantidad: 0")
                return False
            
            store_bets(bets)
            cantidad = len(bets)
            logging.info(f"action: apuesta_recibida | result: success | cantidad: {cantidad}")
            self.send_response(True)
            return True
            
        except Exception as e:
            self.send_response(False, str(e))
            logging.info(f"action: apuesta_recibida | result: fail | cantidad: 0")
            return False

    def handle_finished_notification(self, message):
        """Maneja notificación de que una agencia terminó de enviar apuestas"""
        try:
            parts = message.split('|')
            if len(parts) != 2:
                self.send_response(False, "Invalid FINISHED format")
                return False
            
            agency_id = parts[1]
            
            all_ready = self.state.notify_agency_finished(agency_id)
            
            if all_ready and not self.state.sorteo_realizado:
                self.state.perform_sorteo()
            
            self.send_response(True)
            return True
            
        except Exception as e:
            logging.error(f"action: handle_finished_notification | result: error | error: {e}")
            self.send_response(False, str(e))
            return False

    def handle_winners_query(self, message):
        """Maneja consulta de ganadores de una agencia"""
        try:
            parts = message.split('|')
            if len(parts) != 2:
                self.send_response(False, "Invalid QUERY_WINNERS format")
                return False
            
            agency_id = parts[1]
            
            if self.state.is_sorteo_done():
                self._notify_all_waiting_clients()
            
            if self.state.sorteo_realizado:
                winners = self.state.winners_cache.get(agency_id, [])
                winners_str = ','.join(winners) if winners else ""
                self.send_message(f"WINNERS|{len(winners)}|{winners_str}")
                return True
            
            ServerProtocol.clients_waiting_winners[agency_id] = self.client_socket
            
            return True
            
        except Exception as e:
            logging.error(f"action: handle_winners_query | result: error | error: {e}")
            self.send_response(False, str(e))
            return False
        
    def _notify_all_waiting_clients(self):
        """Envía ganadores a todos los clientes esperando"""
        original_socket = self.client_socket
        
        for agency_id, socket in ServerProtocol.clients_waiting_winners.items():
            try:
                self.client_socket = socket

                winners = self.state.winners_cache.get(agency_id, [])
                winners_str = ','.join(winners) if winners else ""
                self.send_message(f"WINNERS|{len(winners)}|{winners_str}")
                
            except Exception as e:
                logging.error(f"Error notifying agency {agency_id}: {e}")
        
        self.client_socket = original_socket
        
        ServerProtocol.clients_waiting_winners.clear()
        
    def send_message(self, message):
        """Envía un mensaje con longitud al principio"""
        data = message.encode('utf-8')
        header = struct.pack('!I', len(data))
        self._send_complete(header)
        self._send_complete(data)
    
    def send_response(self, success, error_message=None):
        """Envía respuesta al cliente"""
        if success:
            self.send_message("OK")
        else:
            self.send_message(f"ERROR|{error_message or 'Unknown error'}")
    
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
    
    def parse_batch(self, message):
        """Parsea mensaje con formato: BATCH|cantidad|apuesta1|apuesta2|..."""
        try:
            parts = message.split('|')
            if parts[0] != 'BATCH':
                return None, "Invalid batch format"
            
            cantidad = int(parts[1])
            expected_fields = 2 + (cantidad * 6)
            
            if len(parts) != expected_fields:
                return None, f"Expected {expected_fields} fields, got {len(parts)}"
            
            bets = []
            for i in range(cantidad):
                base_idx = 2 + (i * 6)
                agency = parts[base_idx]
                first_name = parts[base_idx + 1]
                last_name = parts[base_idx + 2]
                document = parts[base_idx + 3]
                birthdate = parts[base_idx + 4]
                number = parts[base_idx + 5]
                
                bet = Bet(agency, first_name, last_name, document, birthdate, number)
                bets.append(bet)
            
            return bets, None
        
        except Exception as e:
            return None, str(e)