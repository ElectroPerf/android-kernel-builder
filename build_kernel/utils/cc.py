from build_kernel import prebuilts_path, get_config
from build_kernel.utils.config import Config
from build_kernel.utils.logging import LOGI
from git import Repo
from multiprocessing import cpu_count
import os
from subprocess import Popen, PIPE, STDOUT

TOOLCHAINS_REMOTE = "https://github.com/SebaUbuntu/android-kernel-builder"
CLANG_VERSION = "r383902b"
GCC_VERSION = "4.9"

CLANG_PATH = prebuilts_path / "clang" / "linux-x86" / f"clang-{CLANG_VERSION}"
GCC_PATH = prebuilts_path / "gcc" / "linux-x86"
GCC_AARCH64_PATH = GCC_PATH / "aarch64" / f"aarch64-linux-android-{GCC_VERSION}"
GCC_ARM_PATH = GCC_PATH / "arm" / f"arm-linux-androideabi-{GCC_VERSION}"

class Make:
	def __init__(self, config: Config):
		self.config = config

		# Create environment variables
		self.env_vars = os.environ.copy()
		self.env_vars['PATH'] = f"{CLANG_PATH}/bin:{GCC_AARCH64_PATH}/bin:{GCC_ARM_PATH}/bin:{self.env_vars['PATH']}"

		# Create Make flags
		self.make_flags = [
			f"O={config.out_path}/KERNEL_OBJ",
			f"ARCH={config.arch}",
			f"SUBARCH={config.arch}",
			f"-j{cpu_count()}",
		]

		if config.arch == "arm64":
			self.make_flags.append("CROSS_COMPILE=aarch64-linux-android-")
			self.make_flags.append("CROSS_COMPILE_ARM32=arm-linux-androideabi-")
		else:
			self.make_flags.append("CROSS_COMPILE=arm-linux-androideabi-")

		if get_config("ENABLE_CCACHE") == "true":
			self.make_flags.append(f"CC=ccache clang")
		else:
			self.make_flags.append(f"CC=clang")

		if config.arch == "arm64":
			self.make_flags.append("CLANG_TRIPLE=aarch64-linux-gnu-")
		else:
			self.make_flags.append("CLANG_TRIPLE=arm-linux-gnu-")

		localversion = ""
		kernel_name = get_config("COMMON_KERNEL_NAME")
		kernel_version = get_config("COMMON_KERNEL_VERSION")
		if kernel_name != "":
			localversion += f"-{kernel_name}"
		if kernel_version != "":
			localversion += f"-{kernel_version}"

		if localversion:
			self.make_flags.append(f"LOCALVERSION={localversion}")

		self.make_flags += config.additional_make_flags

		# Clone toolchains if needed
		for toolchain in ["clang", "gcc"]:
			toolchain_path = prebuilts_path / toolchain
			if toolchain_path.is_dir():
				continue

			LOGI(f"Cloning toolchain: {toolchain}")
			Repo.clone_from(TOOLCHAINS_REMOTE, toolchain_path, branch=f"prebuilts-{toolchain}",
							single_branch=True, depth=1)
			LOGI("Cloning finished")

	def run(self, target: str = None):
		command = ["make"]
		command.extend(self.make_flags)
		if target is not None:
			command.append(target)

		process = Popen(command, env=self.env_vars, stdout=PIPE, stderr=STDOUT,
						cwd=self.config.kernel_path, encoding="UTF-8")
		while True:
			output = process.stdout.readline()
			if output == '' and process.poll() is not None:
				break
			if output:
				print(output.strip())
		rc = process.poll()
		if rc != 0:
			make_command = "make"
			if target is not None:
				make_command += f" {target}"

			raise RuntimeError(f"{make_command} failed, return code {rc}")

		return rc
