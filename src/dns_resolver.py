import socket

try:
    import dns.resolver
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False

class DnsResolver:
    def __init__(self, log_callback=None):
        self.log_callback = log_callback
        self.original_getaddrinfo = None
    
    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)
    
    def enable(self):
        if not DNS_AVAILABLE:
            self.log("WARNING: dnspython not installed, DNS bypass disabled")
            return
        
        self.log("Setting up custom DNS (8.8.8.8, 1.1.1.1)...")
        self.original_getaddrinfo = socket.getaddrinfo
        
        def custom_getaddrinfo(host, port, family=0, socktype=0, proto=0, flags=0):
            if 'youtube.com' in host or 'googlevideo.com' in host or 'ytimg.com' in host:
                try:
                    resolver = dns.resolver.Resolver()
                    resolver.nameservers = ['8.8.8.8', '1.1.1.1', '8.8.4.4']
                    resolver.timeout = 5
                    resolver.lifetime = 5
                    
                    try:
                        answers = resolver.resolve(host, 'A')
                        ip = str(answers[0])
                        self.log(f"DNS resolved: {host} -> {ip}")
                        return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', (ip, port))]
                    except:
                        try:
                            answers = resolver.resolve(host, 'AAAA')
                            ip = str(answers[0])
                            self.log(f"DNS resolved (IPv6): {host} -> {ip}")
                            return [(socket.AF_INET6, socket.SOCK_STREAM, 6, '', (ip, port, 0, 0))]
                        except:
                            pass
                except Exception as e:
                    self.log(f"Custom DNS failed for {host}: {e}")
            
            return self.original_getaddrinfo(host, port, family, socktype, proto, flags)
        
        socket.getaddrinfo = custom_getaddrinfo
        self.log("Custom DNS enabled")
    
    def disable(self):
        if self.original_getaddrinfo:
            socket.getaddrinfo = self.original_getaddrinfo
            self.log("Restored original DNS")