import json
import os
from typing import Dict, Optional


class Database:
    """Простая база данных для хранения баланса пользователей"""
    
    def __init__(self, filename: str = "users_data.json"):
        self.filename = filename
        self.data = self.load()
    
    def load(self) -> Dict:
        """Загружает данные из файла"""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    def save(self):
        """Сохраняет данные в файл"""
        with open(self.filename, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
    
    def get_user(self, user_id: int) -> Dict:
        """Получает информацию пользователя или создаёт новую"""
        user_id_str = str(user_id)
        
        if user_id_str not in self.data:
            self.data[user_id_str] = {
                'balance': 1000,
                'total_won': 0,
                'total_lost': 0,
                'games_played': 0,
            }
            self.save()
        
        return self.data[user_id_str]
    
    def add_balance(self, user_id: int, amount: int):
        """Добавляет деньги к балансу пользователя"""
        user = self.get_user(user_id)
        user['balance'] += amount
        
        if amount > 0:
            user['total_won'] += amount
        else:
            user['total_lost'] += abs(amount)
        
        user['games_played'] += 1
        self.save()
    
    def set_balance(self, user_id: int, amount: int):
        """Устанавливает баланс пользователя"""
        user = self.get_user(user_id)
        user['balance'] = amount
        self.save()
    
    def get_balance(self, user_id: int) -> int:
        """Получает баланс пользователя"""
        user = self.get_user(user_id)
        return user['balance']
    
    def get_stats(self, user_id: int) -> Dict:
        """Получает статистику пользователя"""
        return self.get_user(user_id)
