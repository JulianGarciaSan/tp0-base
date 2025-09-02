
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
