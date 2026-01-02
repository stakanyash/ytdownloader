class DownloadQueue:  
    def __init__(self):
        self.items = []
    
    def add(self, url):
        if url in self.items:
            return False
        self.items.append(url)
        return True
    
    def remove(self, index):
        if 0 <= index < len(self.items):
            del self.items[index]
    
    def clear(self):
        self.items.clear()
    
    def next(self):
        return self.items.pop(0) if self.items else None
    
    def peek(self):
        return self.items[0] if self.items else None
    
    def __len__(self):
        return len(self.items)
    
    def __iter__(self):
        return iter(self.items)