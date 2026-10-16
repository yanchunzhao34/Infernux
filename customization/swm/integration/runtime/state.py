"""One shared session for native panels, browser tools and the scene host."""
import threading
from .swm_core.session import Session

lock = threading.RLock()
session = Session()
