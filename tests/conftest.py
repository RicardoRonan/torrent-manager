import os
import tempfile

os.environ.setdefault("TM_CONFIG_DIR", tempfile.mkdtemp(prefix="tm-cfg-"))
os.environ.setdefault("TM_STATE_DIR", tempfile.mkdtemp(prefix="tm-state-"))
