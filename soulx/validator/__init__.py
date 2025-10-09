import argparse
import os
from typing import Optional

import logging as python_logging

from bittensor import Subtensor, config, logging, axon
from bittensor_wallet import Wallet
from tabulate import tabulate


from soulx.core.constants import BLOCK_TIME, DEFAULT_BLACKLIST, TESTNET_NETUID

from soulx.validator.storage import (
    JsonValidatorStorage,
    RedisValidatorStorage,
    get_validator_storage,
)

class BaseValidator:
    def __init__(self):
        """Base initialization for all validator instances."""
        self.config = self.get_config()

        blacklist_str = os.getenv("VALIDATOR_BLACKLIST", "")
        self.config.blacklist = [addr.strip() for addr in
                                 blacklist_str.split(",")] if blacklist_str else DEFAULT_BLACKLIST

        self.setup_logging_path()
        self.setup_logging()
        self.storage = get_validator_storage(
            storage_type=self.config.storage, config=self.config
        )

        self.subtensor = None
        self.wallet = None
        self.metagraph = None
        self.metagraph_info = None
        self.tempo = None
        self.uid = None
        self.validator_hotkey = None
        self.validator_ss58_address = None
        self.weights_interval = None

        self.eval_interval = self.config.eval_interval

        self.last_update = 0
        self.current_block = 0
        self.scores = []
        self.moving_avg_scores = []
        self.hotkeys = []
        self.block_at_registration = []

    def get_config(self):
        """Create and parse configuration."""
        parser = argparse.ArgumentParser()
        self.add_args(parser)
        return config(parser)

    def add_args(self, parser: argparse.ArgumentParser):
        """Base validator argument definitions."""
        parser.add_argument(
            "--worker_prefix",
            required=False,
            default="",
            help="A prefix for the workers names miners will use.",
        )
        parser.add_argument(
            "--netuid",
            type=int,
            default=os.getenv("NETUID", TESTNET_NETUID),
            help="The chain subnet uid.",
        )
        parser.add_argument(
            "--subtensor.network",
            default=os.getenv("SUBTENSOR_NETWORK", "finney"),
            help="The chain subnet network.",
        )
        # 添加 axon 相关参数
        parser.add_argument(
            "--axon.ip",
            type=str,
            default=os.getenv("AXON_IP", "0.0.0.0"),
            help="The IP address to serve the axon on.",
        )
        parser.add_argument(
            "--axon.port",
            type=int,
            default=int(os.getenv("AXON_PORT", "8092")),
            help="The port to serve the axon on.",
        )
        parser.add_argument(
            "--min_blocks_per_validator",
            type=int,
            default=int(os.getenv("MIN_BLOCKS_PER_VALIDATOR", 40)),
            help="Minimum blocks required per validator",
        )
        parser.add_argument(
            "--eval_interval",
            type=int,
            default=25,
            help="The interval on which to run evaluation across the metagraph.",
        )
        parser.add_argument(
            "--state",
            type=str,
            choices=["restore", "fresh"],
            default="restore",
            help="Whether to restore previous validator state ('restore') or start fresh ('fresh').",
        )
        parser.add_argument(
            "--storage",
            type=str,
            choices=["json", "redis"],
            default=os.getenv("STORAGE_TYPE", "json"),
            help="Storage type to use (json or redis)",
        )

        # 配置日志参数
        parser.add_argument(
            "--logging.info",
            action="store_true",
            help="Enable debug logging.",
            default=False
        )
        parser.add_argument(
            "--logging.record_log",
            action="store_true",
            help="Enable recording logs to file.",
            default=True
        )
        parser.add_argument(
            "--logging.level",
            type=str,
            choices=["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            default=os.getenv("BT_LOGGING_INFO", "INFO"),
            help="Logging level."
        )

        parser.add_argument(
            "--neuron.axon_off",
            "--axon_off",
            action="store_true",
            # Note: the validator needs to serve an Axon with their IP or they may
            #   be blacklisted by the firewall of serving peers on the network.
            help="Set this flag to not attempt to serve an Axon.",
            default=True,
        )

        # Other argument providers
        Subtensor.add_args(parser)
        logging.add_args(parser)
        Wallet.add_args(parser)
        JsonValidatorStorage.add_args(parser)
        RedisValidatorStorage.add_args(parser)

    def setup_logging_path(self) -> None:
        """Set up logging directory."""
        self.config.full_path = os.path.expanduser(
            "{}/{}/{}/netuid{}/{}".format(
                self.config.logging.logging_dir,
                self.config.wallet.name,
                self.config.wallet.hotkey,
                self.config.netuid,
                "validator",
            )
        )
        # Ensure the logging directory exists.
        os.makedirs(self.config.full_path, exist_ok=True)

    def setup_logging(self) -> None:
        """Initialize logging configuration."""
        # 初始化日志目录
        self.config.logging.logging_dir = self.config.full_path
        self.config.logging.record_log = True
        logging(config=self.config)

        # 设置日志级别
        if self.config.logging.level == "TRACE":
            logging.set_trace(True)
        else:
            logging.set_trace(False)
            if self.config.logging.level == "DEBUG":
                logging.debug()
            elif self.config.logging.level == "INFO":
                logging.info()
            elif self.config.logging.level == "WARNING":
                logging.warning()
            elif self.config.logging.level == "ERROR":
                logging.error()
            elif self.config.logging.level == "CRITICAL":
                logging.critical()
        
        # 确保日志配置生效
        python_logging.getLogger("bittensor").setLevel(
            getattr(python_logging, self.config.logging.level)
        )
        
        logging.info(
            f"Running validator for subnet: {self.config.netuid} on network: {self.config.subtensor.network} with config:\n{self.config}"
        )

    def setup_bittensor_objects(self) -> None:
        """
        Setup Bittensor objects.
        1. Initialize wallet.
        2. Initialize subtensor.
        3. Initialize metagraph.
        4. Ensure validator is registered to the network.
        """
        # Build Bittensor validator objects.
        logging.info("Setting up Bittensor objects.")

        # Initialize wallet.
        self.wallet = Wallet(config=self.config)
        logging.info(f"Wallet: {self.wallet}")

        # Initialize subtensor.
        self.subtensor = Subtensor(config=self.config)
        logging.info(f"Subtensor: {self.subtensor}")

        # Initialize metagraph.
        self.metagraph = self.subtensor.metagraph(self.config.netuid)
        self.metagraph_info = self.subtensor.get_metagraph_info(self.config.netuid)
        self.metagraph.sync(subtensor=self.subtensor)  # 同步最新状态
        logging.info(f"Metagraph: "
                     f"<netuid:{self.metagraph.netuid}, "
                     f"n:{len(self.metagraph.axons)}, "
                     f"block:{self.metagraph.block}, "
                     f"network: {self.subtensor.network}>")

        # Connect the validator to the network.
        if self.wallet.hotkey.ss58_address not in self.metagraph.hotkeys:
            logging.error(
                f"\nYour validator: {self.wallet}"
                f" is not registered to chain connection: {self.subtensor}"
                f"\nRun 'btcli register' and try again."
            )
            exit()
        else:
            # Each validator gets a unique identity (UID) in the network.
            self.uid = self.metagraph.hotkeys.index(self.wallet.hotkey.ss58_address)
            self.validator_hotkey = self.wallet.hotkey.ss58_address
            logging.info(f"Running validator on uid: {self.uid}")

        self.current_block = self.metagraph.block
        self.hotkeys = self.metagraph.hotkeys
        self.block_at_registration = self.metagraph.block_at_registration
        self.scores = [0.0] * len(self.metagraph.total_stake)
        self.moving_avg_scores = [0.0] * len(self.metagraph.total_stake)
        self.tempo = self.subtensor.tempo(self.config.netuid)

        if not self.config.neuron.axon_off:
            self.serve_axon()
        else:
            logging.warning("axon off, not serving ip to chain.")

    def save_state(self) -> None:
        """Save the current validator state to storage."""
        state = {
            "scores": self.scores,
            "moving_avg_scores": self.moving_avg_scores,
            "hotkeys": self.hotkeys,
            "block_at_registration": self.block_at_registration,
            "current_block": self.current_block,
        }
        self.storage.save_state(state)
        logging.info(f"Saved validator state at block {self.current_block}")

    def resync_metagraph(self) -> None:
        """
        Resyncs the metagraph and updates the score arrays to handle:
        1. New registrations (metagraph size increase)
        2. Hotkey replacements at existing UIDs
        """
        logging.info("Resyncing metagraph...")

        previous_hotkeys = self.hotkeys

        # Sync metagraph
        self.metagraph = self.subtensor.metagraph(self.config.netuid)
        self.metagraph.sync(subtensor=self.subtensor)  # 同步最新状态
        self.current_block = self.metagraph.block

        # Check for changes
        if previous_hotkeys == self.metagraph.hotkeys:
            logging.debug("No metagraph changes detected")
            return

        logging.info("Metagraph updated, handling registrations and replacements")

        # 1. Handle hotkey replacements at existing UIDs
        for uid, hotkey in enumerate(previous_hotkeys):
            if (
                uid < len(self.metagraph.hotkeys)
                and hotkey != self.metagraph.hotkeys[uid]
            ):
                logging.info(
                    f"Hotkey replaced at uid {uid}: {hotkey} -> {self.metagraph.hotkeys[uid]}"
                )
                # Reset scores for replaced hotkeys
                self.scores[uid] = 0.0
                self.moving_avg_scores[uid] = 0.0

        # 2. Handle new registrations
        if len(previous_hotkeys) < len(self.metagraph.hotkeys):
            old_size = len(previous_hotkeys)
            new_size = len(self.metagraph.hotkeys)
            logging.info(f"Metagraph size increased from {old_size} to {new_size}")

            new_scores = [0.0] * new_size
            new_moving_avg = [0.0] * new_size

            # Copy existing scores to the new arrays
            for i in range(min(old_size, len(self.scores))):
                new_scores[i] = self.scores[i]
                new_moving_avg[i] = self.moving_avg_scores[i]

            self.scores = new_scores
            self.moving_avg_scores = new_moving_avg

            # Log new registrations
            for uid in range(old_size, new_size):
                logging.info(
                    f"New registration at uid {uid}: {self.metagraph.hotkeys[uid]}"
                )

        self.hotkeys = self.metagraph.hotkeys
        self.block_at_registration = self.metagraph.block_at_registration
        logging.info(f"Metagraph sync complete at block {self.current_block}")

    def get_burn_uid(self) -> Optional[int]:
        """
        Get the UID of the subnet owner.
        """
        sn_owner_hotkey = self.subtensor.query_subtensor(
            "SubnetOwnerHotkey",
            params=[self.config.netuid],
        )
        owner_uid = self.metagraph.hotkeys.index(sn_owner_hotkey)
        return owner_uid

    def get_next_sync_block(self) -> tuple[int, str]:
        """
        Calculate the next block to sync at.
        Returns:
            tuple[int, str]: (next_block, sync_reason)
            - next_block: the block number to sync at
            - sync_reason: reason for the sync ("Regular sync" or "Weights due")
        """
        sync_reason = "Regular sync"
        next_sync = self.current_block + self.eval_interval

        blocks_since_last_weights = self.subtensor.blocks_since_last_update(
            self.config.netuid, self.uid
        )
        # Calculate when we'll need to set weights
        blocks_until_weights = self.weights_interval - blocks_since_last_weights
        next_weights_block = self.current_block + blocks_until_weights + 1

        if blocks_since_last_weights >= self.weights_interval:
            sync_reason = "Weights due"
            return self.current_block + 1, sync_reason

        elif next_weights_block <= next_sync:
            sync_reason = "Weights due"
            return next_weights_block, sync_reason

        return next_sync, sync_reason

    def ensure_validator_permit(self) -> None:
        """
        Ensure the validator has a permit to participate in the network.
        If not, wait for the next step.
        """
        validator_permits = self.subtensor.query_subtensor(
            "ValidatorPermit",
            params=[self.config.netuid],
        ).value
        if not validator_permits[self.uid]:
            logging.info(f"not permitted self.current_block in {self.current_block}")
            blocks_since_last_step = 0
            try:
                blocks_since_last_step = self.subtensor.query_subtensor(
                    "BlocksSinceLastStep",
                    block=self.current_block,
                    params=[self.config.netuid],
                ).value
            except Exception as e:
                logging.info(f"获取 BlocksSinceLastStep 失败: {e}")
                # blocks_since_last_step = None  # 或者设置为默认值，例如 0
            time_to_wait = (self.tempo - blocks_since_last_step) * BLOCK_TIME + 0.1
            logging.error(
                f"Validator permit not found. Waiting {time_to_wait} seconds."
            )
            target_block = self.current_block + (self.tempo - blocks_since_last_step)
            self.subtensor.wait_for_block(target_block)

    def serve_axon(self):
        """Serve axon to enable external connections."""

        logging.info("serving ip to chain...")
        try:
            # 设置 axon 的 IP 地址
            if not self.config.axon.ip:
                self.config.axon.ip = "0.0.0.0"  # 默认监听所有接口

            # 如果没有设置端口，使用默认端口
            if not self.config.axon.port:
                self.config.axon.port = 8091  # 默认端口

            # 创建并启动 axon
            self.axon = axon(wallet=self.wallet, config=self.config)
            self.axon.start()

            try:
                self.subtensor.serve_axon(
                    netuid=self.config.netuid,
                    axon=self.axon,
                )
                logging.info(
                    f"Running validator {self.axon} on network: {self.config.subtensor.chain_endpoint} with netuid: {self.config.netuid}"
                )
            except Exception as e:
                logging.error(f"Failed to serve Axon with exception: {e}")
                pass

        except Exception as e:
            logging.error(
                f"Failed to create Axon initialize with exception: {e}"
            )
            pass
    def _log_weights_and_scores(self, weights: list[float]) -> None:
        """Log weights and moving average scores in a tabular format."""
        rows = []
        headers = ["UID", "Hotkey", "Moving Avg", "Weight", "Normalized (%)"]

        # Sort by weight (highest first)
        sorted_indices = sorted(
            range(len(weights)), key=lambda w: weights[w], reverse=True
        )

        for i in sorted_indices:
            if weights[i] > 0 or self.moving_avg_scores[i] > 0:
                hotkey = self.metagraph.hotkeys[i]
                rows.append(
                    [
                        i,
                        f"{hotkey}",
                        f"{self.moving_avg_scores[i]:.8f}",
                        f"{weights[i]:.8f}",
                        f"{weights[i] * 100:.2f}%",
                    ]
                )

        if not rows:
            logging.info(f"No miners receiving weights at Block {self.current_block}")
            return

        table = tabulate(
            rows, headers=headers, tablefmt="grid", numalign="right", stralign="left"
        )
        title = f"Weights set at Block: {self.current_block}"
        logging.info(f"{title}\n{table}")

    def _log_scores(self, coin: str, hash_price: float) -> None:
        """Log current scores in a tabular format with hotkeys."""
        rows = []
        headers = ["UID", "Hotkey", "Score", "Moving Avg"]

        # Sort by score (highest first)
        sorted_indices = sorted(
            range(len(self.scores)), key=lambda s: self.scores[s], reverse=True
        )

        for i in sorted_indices:
            if self.scores[i] > 0 or self.moving_avg_scores[i] > 0:
                hotkey = self.metagraph.hotkeys[i]
                rows.append(
                    [
                        i,
                        f"{hotkey}",
                        f"{self.scores[i]:.8f}",
                        f"{self.moving_avg_scores[i]:.8f}",
                    ]
                )

        if not rows:
            logging.info(
                f"No active miners for {coin} (hash price: ${hash_price:.8f}) at Block {self.current_block}"
            )
            return

        table = tabulate(
            rows, headers=headers, tablefmt="grid", numalign="right", stralign="left"
        )

        title = f"Current Mining Scores - Block {self.current_block} - {coin.upper()} (Hash Price: ${hash_price:.8f})"
        logging.info(f"Scores updated at block {self.current_block}")
        logging.info(f".\n{title}\n{table}")
