"""
Movement Limiter: 限制agent在各个方向的移动次数，并处理转向导致的方向变化
"""


class MovementLimiter:
    """
    限制agent的移动次数，考虑转向对方向的影响
    
    核心思想：
    - 使用counter跟踪相对于初始朝向的旋转：look_right +1, look_left -1
    - counter % 4 确定当前朝向（0=前, 1=右, 2=后, 3=左）
    - 将当前朝向下的移动映射到初始朝向的方向
    - 使用净移动次数进行限制：相反方向的移动会相互抵消
      * forward-backward: forward +1, backward -1，限制净移动的绝对值
      * left-right: left +1, right -1，限制净移动的绝对值
      * up-down: up +1, down -1，限制净移动的绝对值
    
    示例：
    - 限制为2时，向前2次(+2)，向后1次(-1)，再向前1次(+1)
    - 净移动 = +2-1+1 = +2，绝对值2 <= 限制2，允许
    """
    
    # 方向映射：当前朝向 -> {当前动作: 初始方向}
    # 朝向: 0=前, 1=右, 2=后, 3=左
    DIRECTION_MAPPING = {
        0: {  # 朝前（初始朝向）
            'move_forward': 'forward',
            'move_backward': 'backward',
            'move_left': 'left',
            'move_right': 'right',
        },
        1: {  # 朝右（相对初始朝向右转90度）
            'move_forward': 'right',    # 朝右时向前走 = 初始朝向的向右
            'move_backward': 'left',    # 朝右时向后走 = 初始朝向的向左
            'move_left': 'forward',     # 朝右时向左走 = 初始朝向的向前
            'move_right': 'backward',   # 朝右时向右走 = 初始朝向的向后
        },
        2: {  # 朝后（相对初始朝向转180度）
            'move_forward': 'backward',
            'move_backward': 'forward',
            'move_left': 'right',
            'move_right': 'left',
        },
        3: {  # 朝左（相对初始朝向左转90度）
            'move_forward': 'left',     # 朝左时向前走 = 初始朝向的向左
            'move_backward': 'right',   # 朝左时向后走 = 初始朝向的向右
            'move_left': 'backward',    # 朝左时向左走 = 初始朝向的向后
            'move_right': 'forward',    # 朝左时向右走 = 初始朝向的向前
        },
    }
    
    def __init__(self, max_horizontal_moves=2, max_up_moves=1):
        """
        初始化移动限制器
        
        Args:
            max_horizontal_moves: 每个水平方向对（前后、左右）的最大净移动次数
            max_up_moves: 向上移动的最大次数
        """
        self.max_horizontal_moves = max_horizontal_moves
        self.max_up_moves = max_up_moves
        
        # 朝向计数器：look_right +1, look_left -1
        self.rotation_counter = 0
        
        # 净移动计数（相对于初始位置）
        # forward-backward: forward +1, backward -1
        # left-right: left +1, right -1
        # up-down: up +1, down -1
        self.net_movements = {
            'forward_backward': 0,  # 正值表示向前，负值表示向后
            'left_right': 0,        # 正值表示向左，负值表示向右
            'up_down': 0,           # 正值表示向上，负值表示向下
        }
        
        # 动作历史
        self.action_history = []
    
    def get_current_facing(self):
        """
        获取当前朝向（相对于初始朝向）
        
        Returns:
            int: 0=前, 1=右, 2=后, 3=左
        """
        return self.rotation_counter % 4
    
    def get_initial_direction(self, action):
        """
        将当前朝向下的动作映射到初始朝向的方向
        
        Args:
            action: 当前动作（如'move_forward'）
            
        Returns:
            str: 相对于初始朝向的方向，如果不是移动动作则返回None
        """
        # 处理上下移动（不受朝向影响）
        if action == 'move_up':
            return 'up'
        elif action == 'move_down':
            return 'down'
        
        # 处理水平移动
        horizontal_moves = ['move_forward', 'move_backward', 'move_left', 'move_right']
        if action in horizontal_moves:
            facing = self.get_current_facing()
            return self.DIRECTION_MAPPING[facing][action]
        
        return None
    
    def can_perform_action(self, action):
        """
        检查是否可以执行该动作（是否超过限制）
        使用净移动次数进行限制检查
        
        Args:
            action: 动作名称
            
        Returns:
            tuple: (bool: 是否可以执行, str: 原因/错误信息)
        """
        # 转向动作总是允许
        if action in ['look_left', 'look_right', 'look_up', 'look_down']:
            return True, "Turn action allowed"
        
        # 获取该动作对应的初始方向
        initial_dir = self.get_initial_direction(action)
        
        if initial_dir is None:
            # 非移动动作，允许
            return True, "Non-movement action allowed"
        
        # 检查上下移动限制（使用净移动）
        if initial_dir == 'up':
            # 向上移动：+1
            new_net = self.net_movements['up_down'] + 1
            if abs(new_net) > self.max_up_moves:
                return False, f"Up movement limit reached (net: {new_net}, limit: {self.max_up_moves})"
            return True, "Up movement allowed"
        
        if initial_dir == 'down':
            # 向下移动：-1
            new_net = self.net_movements['up_down'] - 1
            if abs(new_net) > self.max_up_moves:
                return False, f"Down movement limit reached (net: {new_net}, limit: {self.max_up_moves})"
            return True, "Down movement allowed"
        
        # 检查前后方向限制（使用净移动）
        if initial_dir == 'forward':
            # 向前移动：+1
            new_net = self.net_movements['forward_backward'] + 1
            if abs(new_net) > self.max_horizontal_moves:
                return False, f"Forward movement limit reached (net: {new_net}, limit: {self.max_horizontal_moves})"
            return True, "Forward movement allowed"
        
        if initial_dir == 'backward':
            # 向后移动：-1
            new_net = self.net_movements['forward_backward'] - 1
            if abs(new_net) > self.max_horizontal_moves:
                return False, f"Backward movement limit reached (net: {new_net}, limit: {self.max_horizontal_moves})"
            return True, "Backward movement allowed"
        
        # 检查左右方向限制（使用净移动）
        if initial_dir == 'left':
            # 向左移动：+1
            new_net = self.net_movements['left_right'] + 1
            if abs(new_net) > self.max_horizontal_moves:
                return False, f"Left movement limit reached (net: {new_net}, limit: {self.max_horizontal_moves})"
            return True, "Left movement allowed"
        
        if initial_dir == 'right':
            # 向右移动：-1
            new_net = self.net_movements['left_right'] - 1
            if abs(new_net) > self.max_horizontal_moves:
                return False, f"Right movement limit reached (net: {new_net}, limit: {self.max_horizontal_moves})"
            return True, "Right movement allowed"
        
        return True, "Action allowed"
    
    def perform_action(self, action):
        """
        执行动作并更新状态
        
        Args:
            action: 动作名称
            
        Returns:
            tuple: (bool: 是否成功, str: 信息)
        """
        # 检查是否可以执行
        can_do, reason = self.can_perform_action(action)
        
        if not can_do:
            return False, reason
        
        # 记录动作历史
        self.action_history.append(action)
        
        # 更新转向计数器
        if action == 'look_right':
            self.rotation_counter += 1
        elif action == 'look_left':
            self.rotation_counter -= 1
        
        # 更新净移动计数
        initial_dir = self.get_initial_direction(action)
        if initial_dir:
            if initial_dir == 'forward':
                self.net_movements['forward_backward'] += 1
            elif initial_dir == 'backward':
                self.net_movements['forward_backward'] -= 1
            elif initial_dir == 'left':
                self.net_movements['left_right'] += 1
            elif initial_dir == 'right':
                self.net_movements['left_right'] -= 1
            elif initial_dir == 'up':
                self.net_movements['up_down'] += 1
            elif initial_dir == 'down':
                self.net_movements['up_down'] -= 1
        
        return True, reason
    
    def get_status(self):
        """
        获取当前状态信息
        
        Returns:
            dict: 状态信息
        """
        facing_names = ['前(初始)', '右', '后', '左']
        facing = self.get_current_facing()
        
        return {
            'rotation_counter': self.rotation_counter,
            'current_facing': facing,
            'facing_name': facing_names[facing],
            'net_movements': self.net_movements.copy(),
            'limits': {
                'horizontal': self.max_horizontal_moves,
                'up': self.max_up_moves,
            },
            'total_actions': len(self.action_history),
        }
    
    def reset(self):
        """重置所有计数器"""
        self.rotation_counter = 0
        self.net_movements = {k: 0 for k in self.net_movements}
        self.action_history = []

