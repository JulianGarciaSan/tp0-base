import threading
import logging
import os
from collections import defaultdict
from common.utils import Bet, has_won, store_bets, load_bets


class LotteryMonitor:    
    
    def __init__(self):
        self.total_agencies = int(os.environ.get('AGENCY_COUNT', 5))
        
        self._agencies_finished = set() 
        self._sorteo_realizado = False
        self._winners_cache = {}
        
        self._monitor_lock = threading.Lock()
        self._sorteo_condition = threading.Condition(self._monitor_lock)
        self._storage_lock = threading.Lock() 

    def add_bets(self, bets):
        try:
            with self._storage_lock:
                store_bets(bets)
            
            return True
            
        except Exception as e:
            logging.error(f"action: add_bets | result: error | error: {e}")
            return False
    
    def notify_agency_finished(self, agency_id):
        with self._sorteo_condition:
            self._agencies_finished.add(agency_id)
            finished_count = len(self._agencies_finished)
            
            all_finished = finished_count == self.total_agencies
            
            if all_finished and not self._sorteo_realizado:
                self._execute_Lottery()
                self._sorteo_condition.notify_all()
            
            return all_finished
    
    def wait_for_winners(self, agency_id):
        with self._sorteo_condition:
            while not self._sorteo_realizado:
                self._sorteo_condition.wait()
            
            winners = self._winners_cache.get(agency_id, [])
            return winners
    
    def _execute_Lottery(self):
        if self._sorteo_realizado:
            return
        
        try:
            all_bets = list(load_bets())
        except Exception as e:
            return
        
        for bet in all_bets:
            agency_id = str(bet.agency)
            
            if agency_id not in self._winners_cache:
                self._winners_cache[agency_id] = []
            
            if has_won(bet):
                self._winners_cache[agency_id].append(bet.document)
        
        self._sorteo_realizado = True
        

    def is_sorteo_completed(self):
        with self._monitor_lock:
            return self._sorteo_realizado

lottery_monitor = LotteryMonitor()