from pathlib import Path
import os

BLOCK_TIME = 12  # Seconds per block

MAIN_PATH = Path(__file__).parent.parent.parent

# 版本号
VERSION_KEY =1101 # 86 2208

# U16最大值
U16_MAX = 65535

# Default allocation strategy
DEFAULT_ALLOCATION_STRATEGY = "stake"  # Options: "stake", "equal"

# Default model configuration
DEFAULT_MODEL_NAME = "Qwen/Qwen2.5-7B-Instruct"

# Default blacklist configuration
DEFAULT_BLACKLIST = []  # Empty list by default

BAD_COLDKEYS = []

# Bittensor units conversion
RAO_TO_TAO = 1_000_000_000  # 1 tao = 1_000_000_000 rao

# 最低质押要求（单位：dtao）
MIN_VALIDATOR_STAKE_DTAO = float(os.getenv("MIN_VALIDATOR_STAKE_DTAO", "1000.0"))  # 验证者最低质押要求，默认1000 dtao
MIN_MINER_STAKE_DTAO = float(os.getenv("MIN_MINER_STAKE_DTAO", "50.0"))  # 矿工最低质押要求，默认50 dtao

TESTNET_NETUID = 356

# 验证者配置
MIN_BLOCKS_PER_VALIDATOR = 10  # 每个验证者的最小区块数

# 任务管理配置
MAX_TASK_POOL_SIZE = 1000  # 任务池最大容量
DEFAULT_TASK_POOL_SIZE = 1000  # 任务池默认容量

OWNER_DEFAULT_SCORE = 0.2

FINAL_MIN_SCORE = 0.8

DEFAULT_PENALTY_COEFFICIENT= 0.000000001

DEFAULT_LOG_PATH = "logs"
MAX_VALIDATOR_BLOCKS = int(os.getenv("MAX_VALIDATOR_BLOCKS", "7200"))
CHECK_NODE_ACTIVE = os.getenv("CHECK_NODE_ACTIVE", "false").lower() == "true"


SCORING_PERIOD_TIME = 60 * 30  # 30 mins
VERSION_KEY = 68200
CHARACTER_TO_TOKEN_CONVERSION = 4.0
INP_TO_OUTP_TXT_WORK_RATIO = 0.2
IMG_WORK_WINDOW = (128, 128)
PROD_NETUID = 115

TASK = "task"
TASK_TYPE = "task_type"
MAX_CAPACITY = "max_capacity"
MODEL_CONFIG = "model_config"
ENDPOINT = "endpoint"
WEIGHT = "weight"
MINER_TYPE = "miner_type"


GPU_WORKER_VERSION_ENDPOINT = "version"

MIN_STEPS = "min_steps"
MAX_STEPS = "max_steps"
