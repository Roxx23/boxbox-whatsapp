import time
import threading
from queue import Queue, Empty
from collections import deque
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Thread-safe rate limiter for WhatsApp Cloud API
    
    WhatsApp Cloud API Limits:
    - 80 messages per second (Business API)
    - 1000 messages per second (Cloud API with approved limits)
    - Recommended: 20-50 messages per second for safety
    """
    
    def __init__(self, max_requests=20, time_window=1.0):
        """
        Initialize rate limiter
        
        Args:
            max_requests: Maximum requests allowed in time_window
            time_window: Time window in seconds (default 1 second)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.requests = deque()
        self.lock = threading.Lock()
    
    def wait_if_needed(self):
        """Block if rate limit is reached"""
        with self.lock:
            now = time.time()
            
            # Remove old requests outside time window
            while self.requests and self.requests[0] < now - self.time_window:
                self.requests.popleft()
            
            # If at limit, wait until oldest request expires
            if len(self.requests) >= self.max_requests:
                sleep_time = self.requests[0] + self.time_window - now
                if sleep_time > 0:
                    logger.info(f"⏳ Rate limit reached. Waiting {sleep_time:.2f}s")
                    time.sleep(sleep_time)
                    # Clean up again after waiting
                    self.requests.popleft()
            
            # Record this request
            self.requests.append(time.time())


class MessageQueue:
    """
    Thread-safe message queue with worker threads
    Handles retries and error recovery
    """
    
    def __init__(self, rate_limiter, num_workers=1):
        """
        Initialize message queue
        
        Args:
            rate_limiter: RateLimiter instance
            num_workers: Number of worker threads (default 1 for sequential sending)
        """
        self.queue = Queue()
        self.rate_limiter = rate_limiter
        self.num_workers = num_workers
        self.workers = []
        self.running = False
        self.results = []
        self.results_lock = threading.Lock()
    
    def add_message(self, send_function, *args, **kwargs):
        """
        Add a message to the queue
        
        Args:
            send_function: The function to call (e.g., send_template, send_text)
            *args, **kwargs: Arguments to pass to send_function
        """
        self.queue.put({
            'function': send_function,
            'args': args,
            'kwargs': kwargs,
            'retries': 0,
            'max_retries': 3
        })
    
    def _worker(self):
        """Worker thread that processes messages from queue"""
        while self.running:
            try:
                # Get message with timeout to allow checking running flag
                message = self.queue.get(timeout=1)
                
                # Rate limit before sending
                self.rate_limiter.wait_if_needed()
                
                # Send the message
                try:
                    status, response = message['function'](
                        *message['args'],
                        **message['kwargs']
                    )
                    
                    # Handle rate limit response (429)
                    if status == 429:
                        if message['retries'] < message['max_retries']:
                            message['retries'] += 1
                            wait_time = 2 ** message['retries']  # Exponential backoff
                            logger.warning(f"⚠️ Rate limited (429). Retry {message['retries']}/{message['max_retries']} in {wait_time}s")
                            time.sleep(wait_time)
                            self.queue.put(message)  # Re-queue
                        else:
                            logger.error(f"❌ Max retries reached for message")
                            self._record_result(message, status, response, failed=True)
                    
                    # Handle other errors
                    elif status >= 400:
                        if message['retries'] < message['max_retries']:
                            message['retries'] += 1
                            logger.warning(f"⚠️ Error {status}. Retry {message['retries']}/{message['max_retries']}")
                            time.sleep(2)
                            self.queue.put(message)  # Re-queue
                        else:
                            logger.error(f"❌ Failed after {message['max_retries']} retries: {response}")
                            self._record_result(message, status, response, failed=True)
                    
                    # Success
                    else:
                        logger.info(f"✅ Message sent successfully")
                        self._record_result(message, status, response, failed=False)
                
                except Exception as e:
                    logger.error(f"❌ Exception sending message: {e}")
                    self._record_result(message, 500, str(e), failed=True)
                
                finally:
                    self.queue.task_done()
            
            except Empty:
                continue  # No message available, continue loop
    
    def _record_result(self, message, status, response, failed):
        """Thread-safe result recording"""
        with self.results_lock:
            self.results.append({
                'status': status,
                'response': response,
                'failed': failed,
                'retries': message['retries'],
                'timestamp': datetime.now()
            })
    
    def start(self):
        """Start worker threads"""
        self.running = True
        for i in range(self.num_workers):
            worker = threading.Thread(target=self._worker, daemon=True)
            worker.start()
            self.workers.append(worker)
        logger.info(f"🚀 Started {self.num_workers} worker thread(s)")
    
    def stop(self):
        """Stop worker threads gracefully"""
        logger.info("⏹️ Stopping workers...")
        self.running = False
        for worker in self.workers:
            worker.join(timeout=5)
        logger.info("✅ All workers stopped")
    
    def wait_completion(self, timeout=None):
        """Wait for all messages to be processed"""
        self.queue.join()
        logger.info("✅ All messages processed")
    
    def get_results(self):
        """Get all results thread-safely"""
        with self.results_lock:
            return self.results.copy()
    
    def get_stats(self):
        """Get processing statistics"""
        with self.results_lock:
            total = len(self.results)
            successful = sum(1 for r in self.results if not r['failed'])
            failed = sum(1 for r in self.results if r['failed'])
            
            return {
                'total': total,
                'successful': successful,
                'failed': failed,
                'success_rate': (successful / total * 100) if total > 0 else 0,
                'pending': self.queue.qsize()
            }


# ==============================================================
# USAGE EXAMPLE
# ==============================================================

if __name__ == "__main__":
    from utils.whatsapp import send_text, send_template
    
    # Initialize rate limiter (20 messages per second)
    rate_limiter = RateLimiter(max_requests=20, time_window=1.0)
    
    # Initialize message queue with 1 worker
    message_queue = MessageQueue(rate_limiter, num_workers=1)
    
    # Start processing
    message_queue.start()
    
    # Add messages to queue
    recipients = [
        {"phone": "+919156143465", "name": "Alice"},
        {"phone": "+919876543210", "name": "Bob"},
        # ... more recipients
    ]
    
    for recipient in recipients:
        # Add text message
        message_queue.add_message(
            send_text,
            recipient['phone'],
            f"Hello {recipient['name']}!"
        )
        
        # OR add template message
        # message_queue.add_message(
        #     send_template,
        #     recipient['phone'],
        #     'your_template_name',
        #     ['param1', 'param2'],
        #     'en_US'
        # )
    
    # Wait for all messages to complete
    message_queue.wait_completion()
    
    # Get statistics
    stats = message_queue.get_stats()
    print(f"\n📊 Statistics:")
    print(f"Total: {stats['total']}")
    print(f"Successful: {stats['successful']}")
    print(f"Failed: {stats['failed']}")
    print(f"Success Rate: {stats['success_rate']:.1f}%")
    
    # Stop workers
    message_queue.stop()