
import logging

from common.utils import Bet

class Parser:
    @staticmethod
    def parse_bet(message):
        parts = message.split('|')
        if len(parts) != 7 or parts[0] != 'BET':
            logging.error(f"action: parse_bet | result: error | error: invalid_format | parts: {len(parts)}")
            return None

        _, agency, first_name, last_name, document, birthdate, number = parts

        bet = Bet(agency, first_name, last_name, document, birthdate, number)
        return bet
    
    @staticmethod
    def parse_batch(message):
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
            logging.error(f"action: parse_batch | result: error | error: {e}")
            return None, str(e)

    @staticmethod
    def parse_winner(message):
        parts = message.split('|')
        if parts[0] != 'WINNERS':
            logging.error(f"action: parse_winner | result: error | error: invalid_format | parts: {len(parts)}")
            return None

        _, agency = parts

        return agency
        
    @staticmethod
    def parse_lot_winner(message):
        winners_str = ','.join(message) if message else ""
        return f"WINNERS|{len(message)}|{winners_str}"