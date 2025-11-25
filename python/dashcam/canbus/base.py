"""
CAN Bus Interface for Active Dash Mirror
Waveshare 2-CH CAN HAT Plus support
Provides base interface for vehicle CAN communication
"""

import can
import logging
import time
from threading import Thread, Event, Lock
from typing import Optional, Callable, Dict, List
from dataclasses import dataclass
from enum import Enum


class CANChannel(Enum):
    """CAN channels on the hat"""
    CAN0 = "can0"
    CAN1 = "can1"


@dataclass
class CANMessage:
    """Represents a CAN message"""
    arbitration_id: int
    data: bytes
    timestamp: float
    channel: str
    is_extended_id: bool = False
    
    def __str__(self):
        data_hex = ' '.join(f'{b:02X}' for b in self.data)
        return f"ID: 0x{self.arbitration_id:03X} [{len(self.data)}] {data_hex}"


class CANBusInterface:
    """Base CAN bus interface for Waveshare 2-CH CAN HAT Plus"""
    
    def __init__(self, config, channel: CANChannel = CANChannel.CAN0, bitrate: int = 500000):
        """
        Initialize CAN bus interface
        
        Args:
            config: System configuration
            channel: CAN channel to use (CAN0 or CAN1)
            bitrate: CAN bus bitrate (default 500000 for most vehicles)
        """
        self.config = config
        self.channel = channel.value
        self.bitrate = bitrate
        self.logger = logging.getLogger(f"CANBus-{channel.value}")
        
        # CAN bus
        self.bus = None
        self.connected = False
        
        # Message handling
        self.message_handlers: Dict[int, List[Callable]] = {}  # ID -> [callbacks]
        self.raw_message_callback: Optional[Callable] = None
        
        # Statistics
        self.messages_received = 0
        self.messages_sent = 0
        self.errors = 0
        self.last_message_time = 0
        
        # Threading
        self.running = False
        self.stop_event = Event()
        self.receive_thread = None
        self.stats_lock = Lock()
        
    def start(self) -> bool:
        """Start CAN bus interface"""
        try:
            self.logger.info(f"Starting CAN bus on {self.channel} @ {self.bitrate} bps...")
            
            # Create CAN bus interface
            self.bus = can.interface.Bus(
                channel=self.channel,
                bustype='socketcan',
                bitrate=self.bitrate
            )
            
            self.connected = True
            
            # Start receive thread
            self.running = True
            self.stop_event.clear()
            self.receive_thread = Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            
            self.logger.info(f"CAN bus started on {self.channel}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to start CAN bus: {e}")
            self.connected = False
            return False
    
    def stop(self):
        """Stop CAN bus interface"""
        self.logger.info("Stopping CAN bus...")
        self.running = False
        self.stop_event.set()
        
        if self.receive_thread:
            self.receive_thread.join(timeout=2.0)
        
        if self.bus:
            try:
                self.bus.shutdown()
            except Exception as e:
                self.logger.error(f"Error shutting down CAN bus: {e}")
            self.bus = None
        
        self.connected = False
        self.logger.info("CAN bus stopped")
    
    def send_message(self, arbitration_id: int, data: bytes, 
                    extended_id: bool = False) -> bool:
        """
        Send a CAN message
        
        Args:
            arbitration_id: CAN message ID
            data: Message data (up to 8 bytes)
            extended_id: True for 29-bit extended ID
            
        Returns:
            True if message sent successfully
        """
        if not self.connected or not self.bus:
            self.logger.error("CAN bus not connected")
            return False
        
        if len(data) > 8:
            self.logger.error(f"Data too long: {len(data)} bytes (max 8)")
            return False
        
        try:
            msg = can.Message(
                arbitration_id=arbitration_id,
                data=data,
                is_extended_id=extended_id
            )
            
            self.bus.send(msg)
            
            with self.stats_lock:
                self.messages_sent += 1
            
            self.logger.debug(f"TX: {self._format_message(msg)}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
            with self.stats_lock:
                self.errors += 1
            return False
    
    def register_handler(self, arbitration_id: int, callback: Callable[[CANMessage], None]):
        """
        Register a callback for specific CAN ID
        
        Args:
            arbitration_id: CAN message ID to listen for
            callback: Function to call when message is received
        """
        if arbitration_id not in self.message_handlers:
            self.message_handlers[arbitration_id] = []
        
        self.message_handlers[arbitration_id].append(callback)
        self.logger.debug(f"Registered handler for ID 0x{arbitration_id:03X}")
    
    def unregister_handler(self, arbitration_id: int, callback: Callable):
        """Unregister a callback for specific CAN ID"""
        if arbitration_id in self.message_handlers:
            try:
                self.message_handlers[arbitration_id].remove(callback)
                if not self.message_handlers[arbitration_id]:
                    del self.message_handlers[arbitration_id]
                self.logger.debug(f"Unregistered handler for ID 0x{arbitration_id:03X}")
            except ValueError:
                pass
    
    def set_raw_message_callback(self, callback: Optional[Callable[[CANMessage], None]]):
        """
        Set callback for all CAN messages (for logging/debugging)
        
        Args:
            callback: Function to call for every received message
        """
        self.raw_message_callback = callback
    
    def _receive_loop(self):
        """Main receive loop for CAN messages"""
        self.logger.info("CAN receive thread started")
        
        while self.running and not self.stop_event.is_set():
            try:
                # Receive message with timeout
                msg = self.bus.recv(timeout=0.1)
                
                if msg is None:
                    continue
                
                # Update stats
                with self.stats_lock:
                    self.messages_received += 1
                    self.last_message_time = time.time()
                
                # Convert to our message format
                can_msg = CANMessage(
                    arbitration_id=msg.arbitration_id,
                    data=bytes(msg.data),
                    timestamp=msg.timestamp,
                    channel=self.channel,
                    is_extended_id=msg.is_extended_id
                )
                
                # Log if debug enabled
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"RX: {can_msg}")
                
                # Call raw message callback if set
                if self.raw_message_callback:
                    try:
                        self.raw_message_callback(can_msg)
                    except Exception as e:
                        self.logger.error(f"Error in raw message callback: {e}")
                
                # Call registered handlers
                if msg.arbitration_id in self.message_handlers:
                    for handler in self.message_handlers[msg.arbitration_id]:
                        try:
                            handler(can_msg)
                        except Exception as e:
                            self.logger.error(
                                f"Error in handler for ID 0x{msg.arbitration_id:03X}: {e}"
                            )
                
            except Exception as e:
                if self.running:  # Only log if we're supposed to be running
                    self.logger.error(f"Error receiving CAN message: {e}")
                    with self.stats_lock:
                        self.errors += 1
                time.sleep(0.1)
        
        self.logger.info("CAN receive thread stopped")
    
    def _format_message(self, msg: can.Message) -> str:
        """Format a CAN message for logging"""
        data_hex = ' '.join(f'{b:02X}' for b in msg.data)
        return f"ID: 0x{msg.arbitration_id:03X} [{msg.dlc}] {data_hex}"
    
    def get_stats(self) -> dict:
        """Get CAN bus statistics"""
        with self.stats_lock:
            return {
                'channel': self.channel,
                'connected': self.connected,
                'bitrate': self.bitrate,
                'messages_received': self.messages_received,
                'messages_sent': self.messages_sent,
                'errors': self.errors,
                'last_message_time': self.last_message_time,
                'handlers_registered': len(self.message_handlers)
            }
    
    def set_filters(self, filters: List[dict]):
        """
        Set CAN filters (hardware filtering)
        
        Args:
            filters: List of filter dicts with 'can_id' and 'can_mask'
                    Example: [{"can_id": 0x100, "can_mask": 0x7FF}]
        """
        if not self.bus:
            self.logger.error("CAN bus not initialized")
            return False
        
        try:
            self.bus.set_filters(filters)
            self.logger.info(f"Set {len(filters)} CAN filters")
            return True
        except Exception as e:
            self.logger.error(f"Failed to set filters: {e}")
            return False


class CANBusMonitor:
    """CAN bus monitor for debugging/logging"""
    
    def __init__(self, canbus: CANBusInterface):
        self.canbus = canbus
        self.logger = logging.getLogger("CANMonitor")
        self.message_counts: Dict[int, int] = {}
        self.monitoring = False
        
    def start_monitoring(self):
        """Start monitoring all CAN messages"""
        self.canbus.set_raw_message_callback(self._on_message)
        self.monitoring = True
        self.logger.info("CAN bus monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring"""
        self.canbus.set_raw_message_callback(None)
        self.monitoring = False
        self.logger.info("CAN bus monitoring stopped")
    
    def _on_message(self, msg: CANMessage):
        """Called for every CAN message"""
        if msg.arbitration_id not in self.message_counts:
            self.message_counts[msg.arbitration_id] = 0
        self.message_counts[msg.arbitration_id] += 1
    
    def get_message_counts(self) -> Dict[int, int]:
        """Get count of messages by ID"""
        return self.message_counts.copy()
    
    def print_summary(self):
        """Print summary of CAN traffic"""
        print("\n" + "="*60)
        print("CAN Bus Traffic Summary")
        print("="*60)
        
        sorted_ids = sorted(self.message_counts.items(), 
                          key=lambda x: x[1], 
                          reverse=True)
        
        for can_id, count in sorted_ids:
            print(f"  0x{can_id:03X}: {count:6d} messages")
        
        print("="*60 + "\n")