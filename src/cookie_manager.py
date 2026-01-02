import os
import tempfile
import browser_cookie3

class CookieManager:
    BROWSER_FUNCTIONS = {
        'chrome': browser_cookie3.chrome,
        'firefox': browser_cookie3.firefox,
        'edge': browser_cookie3.edge,
        'opera': browser_cookie3.opera,
        'brave': browser_cookie3.brave,
        'chromium': browser_cookie3.chromium,
        'vivaldi': browser_cookie3.vivaldi,
    }
    
    @staticmethod
    def extract(browser_choice, log_callback=None):
        if browser_choice == "none":
            return None
        
        def log(msg):
            if log_callback:
                log_callback(msg)
        
        log(f"Extracting cookies from {browser_choice}...")
        
        try:
            cookies = None
            
            if browser_choice == "auto":
                browsers = [
                    ('Chrome', browser_cookie3.chrome),
                    ('Firefox', browser_cookie3.firefox),
                    ('Edge', browser_cookie3.edge),
                    ('Opera', browser_cookie3.opera),
                    ('Brave', browser_cookie3.brave),
                ]
                
                for name, func in browsers:
                    try:
                        cookies = func(domain_name="youtube.com")
                        log(f"Cookies found in {name}")
                        break
                    except:
                        continue
                
                if not cookies:
                    log("No cookies found in any browser")
                    return None
            else:
                if browser_choice in CookieManager.BROWSER_FUNCTIONS:
                    try:
                        cookies = CookieManager.BROWSER_FUNCTIONS[browser_choice](domain_name="youtube.com")
                        log(f"Cookies extracted from {browser_choice.title()}")
                    except Exception as e:
                        log(f"Failed to extract cookies: {e}")
                        return None
            
            if cookies:
                cookies_file = os.path.join(tempfile.gettempdir(), "yt_cookies.txt")
                
                with open(cookies_file, "w", encoding="utf-8") as f:
                    f.write("# Netscape HTTP Cookie File\n")
                    for c in cookies:
                        f.write("\t".join([
                            c.domain,
                            "TRUE" if c.domain.startswith(".") else "FALSE",
                            c.path,
                            "TRUE" if c.secure else "FALSE",
                            str(c.expires or 0),
                            c.name,
                            c.value
                        ]) + "\n")
                
                log("Cookies saved successfully")
                return cookies_file
                
        except Exception as e:
            log(f"Cookie extraction failed: {e}")
        
        return None