import numpy as np
from dataclasses import dataclass


@dataclass
class ChannelState:
    """信道状态数据容器"""

    bs_id: int
    position: np.ndarray  # 基站坐标 [x, y, z]
    distance: float  # 无人机到基站的距离 (m)
    rx_power: float  # 接收功率 (dBm)
    snr: float  # 信噪比 (dB)
    capacity: float  # 信道容量 (Gbps)
    los_status: bool  # 视距是否被遮挡 (True=无障碍)


class BaseStation:
    def __init__(
        self,
        bs_id: int,
        position: np.ndarray,
    ):
        """
        初始化单个基站
        :param bs_id: 基站唯一标识
        :param position: 基站坐标 [x, y, z] (m)
        :param freq: 载波频率 (Hz), 默认140 GHz (太赫兹频段)
        :param tx_power: 发射功率 (dBm), 默认30 dBm (1W)
        """
        self.bs_id = bs_id
        self.position = np.array(position, dtype=np.float32)
        self.freq = 140e9
        self.tx_power = 30.0  # dBm
        self.bandwidth = 1e9  # 带宽 (Hz)
        self.antenna_gain = 30  # 天线增益 (dBi)
        self.noise_figure = 5  # 接收机噪声系数 (dB)

    def calculate_path_loss(
        self, uav_pos: np.ndarray, obstacle_map: np.ndarray = None
    ) -> float:
        """
        计算太赫兹信道路径损耗（含障碍物检测）
        :param uav_pos: 无人机当前位置 [x, y, z]
        :param obstacle_map: 障碍物坐标数组 (Nx3), 用于检测视距遮挡
        :return: 总路径损耗 (dB)
        """
        # 1. 计算自由空间损耗 (Free Space Path Loss)
        distance = np.linalg.norm(uav_pos - self.position)
        fspl = 20 * np.log10(distance) + 20 * np.log10(self.freq) - 147.55

        # 2. 雨衰模型 (ITU-R P.838)
        rain_rate = 5  # 降雨强度 (mm/h), 假设暴雨
        rain_attenuation = 0.01 * rain_rate**1.2 * distance / 1000

        # 3. 分子吸收损耗 (60 GHz氧分子吸收峰附近)
        oxygen_absorption = 0.5 * 1e-3 * distance

        # 4. 障碍物遮挡检测
        los_status = True
        if obstacle_map is not None:
            # 简化的视距检测：检查无人机-基站连线上是否有障碍物
            los_vector = self.position - uav_pos
            for obs in obstacle_map:
                # 计算障碍物到视距线的最短距离
                t = np.dot(obs - uav_pos, los_vector) / np.dot(los_vector, los_vector)
                t = np.clip(t, 0, 1)
                proj = uav_pos + t * los_vector
                dist = np.linalg.norm(obs - proj)
                if dist < 1.0:  # 假设障碍物半径1m
                    los_status = False
                    break

        total_loss = (
            fspl + rain_attenuation + oxygen_absorption + (0 if los_status else 20)
        )
        return total_loss, los_status

    def get_channel_state(
        self, uav_pos: np.ndarray, obstacle_map: np.ndarray = None
    ) -> ChannelState:
        """
        获取当前基站的信道状态
        :param uav_pos: 无人机当前位置 [x, y, z]
        :param obstacle_map: 障碍物坐标数组 (Nx3)
        :return: ChannelState 对象
        """
        # 计算路径损耗
        path_loss, los_status = self.calculate_path_loss(uav_pos, obstacle_map)

        # 接收功率计算
        rx_power = self.tx_power + self.antenna_gain - path_loss - self.noise_figure

        # 信噪比 (dB)
        noise_power = 10 * np.log10(1.38e-23 * 300 * self.bandwidth) + 30  # dBm
        snr = rx_power - noise_power

        # 信道容量 (Gbps)
        capacity = self.bandwidth * np.log2(1 + 10 ** (snr / 10)) / 1e9
        # print(
        #     f"id: {self.bs_id}, rx_power: {rx_power:.2f} dBm, snr: {snr:.2f} dB, capacity: {capacity:.2f} Gbps"
        # )
        return ChannelState(
            bs_id=self.bs_id,
            position=self.position,
            distance=np.linalg.norm(uav_pos - self.position),
            rx_power=rx_power,
            snr=snr,
            capacity=capacity,
            los_status=los_status,
        )
