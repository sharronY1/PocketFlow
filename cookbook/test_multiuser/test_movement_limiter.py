"""
测试脚本：验证MovementLimiter的功能
"""

from movement_limiter import MovementLimiter


def print_separator(title=""):
    """打印分隔线"""
    if title:
        print(f"\n{'='*60}")
        print(f"  {title}")
        print(f"{'='*60}")
    else:
        print("-" * 60)


def print_status(limiter):
    """打印当前状态"""
    status = limiter.get_status()
    print(f"当前朝向: {status['facing_name']} (counter={status['rotation_counter']})")
    print(f"移动统计 (相对于初始朝向):")
    print(f"  前: {status['move_counts']['forward']}/{status['limits']['horizontal']}")
    print(f"  后: {status['move_counts']['backward']}/{status['limits']['horizontal']}")
    print(f"  左: {status['move_counts']['left']}/{status['limits']['horizontal']}")
    print(f"  右: {status['move_counts']['right']}/{status['limits']['horizontal']}")
    print(f"  上: {status['move_counts']['up']}/{status['limits']['up']}")
    print(f"  下: {status['move_counts']['down']} (无限制)")
    print(f"总动作数: {status['total_actions']}")


def test_basic_movement():
    """测试1: 基本移动（不转向）"""
    print_separator("测试1: 基本移动（不转向）")
    
    limiter = MovementLimiter(max_horizontal_moves=3, max_up_moves=2)
    
    actions = [
        'move_forward',   # 向前 1
        'move_forward',   # 向前 2
        'move_left',      # 向左 1
        'move_right',     # 向右 1
        'move_forward',   # 向前 3（达到限制）
        'move_forward',   # 向前 4（应该失败）
    ]
    
    for i, action in enumerate(actions, 1):
        success, reason = limiter.perform_action(action)
        print(f"\n动作 {i}: {action}")
        print(f"  结果: {'[成功]' if success else '[失败]'}")
        print(f"  原因: {reason}")
        if not success:
            print_status(limiter)
    
    print("\n最终状态:")
    print_status(limiter)


def test_rotation_and_movement():
    """测试2: 转向后的移动"""
    print_separator("测试2: 转向后的移动")
    
    limiter = MovementLimiter(max_horizontal_moves=3, max_up_moves=2)
    
    # 场景：向前走2次，右转，再"向前"走（实际是初始朝向的向右）
    actions = [
        'move_forward',   # 初始朝向向前 1
        'move_forward',   # 初始朝向向前 2
        'look_right',     # 右转（counter=1, 朝右）
        'move_forward',   # 当前朝右，向前走 = 初始朝向向右 1
        'move_forward',   # 初始朝向向右 2
        'look_right',     # 再右转（counter=2, 朝后）
        'move_forward',   # 当前朝后，向前走 = 初始朝向向后 1
    ]
    
    for i, action in enumerate(actions, 1):
        success, reason = limiter.perform_action(action)
        print(f"\n动作 {i}: {action}")
        print(f"  结果: {'[成功]' if success else '[失败]'}")
        
        if action.startswith('move'):
            initial_dir = limiter.get_initial_direction(action)
            status = limiter.get_status()
            print(f"  当前朝向: {status['facing_name']}")
            print(f"  映射到初始方向: {initial_dir}")
        elif action.startswith('look'):
            status = limiter.get_status()
            print(f"  转向后朝向: {status['facing_name']}")
    
    print("\n最终状态:")
    print_status(limiter)


def test_negative_rotation():
    """测试3: 负数旋转（左转）"""
    print_separator("测试3: 负数旋转测试")
    
    limiter = MovementLimiter(max_horizontal_moves=3, max_up_moves=2)
    
    # 场景：左转2次再右转1次，验证 counter=-1 % 4 = 3（朝左）
    actions = [
        'move_forward',   # 向前 1
        'look_left',      # 左转（counter=-1, 朝左）
        'look_left',      # 再左转（counter=-2, 朝后）
        'look_right',     # 右转（counter=-1, 朝左）
        'move_forward',   # 当前朝左，向前走 = 初始朝向向左 1
    ]
    
    for i, action in enumerate(actions, 1):
        success, reason = limiter.perform_action(action)
        print(f"\n动作 {i}: {action}")
        
        status = limiter.get_status()
        print(f"  rotation_counter: {status['rotation_counter']}")
        print(f"  当前朝向: {status['facing_name']} (facing={status['current_facing']})")
        
        if action.startswith('move'):
            initial_dir = limiter.get_initial_direction(action)
            print(f"  映射到初始方向: {initial_dir}")
    
    print("\n最终状态:")
    print_status(limiter)


def test_complex_scenario():
    """测试4: 复杂场景 - 多次转向和移动"""
    print_separator("测试4: 复杂场景")
    
    limiter = MovementLimiter(max_horizontal_moves=2, max_up_moves=1)
    
    actions = [
        'move_forward',   # 前 1
        'move_forward',   # 前 2（达到限制）
        'look_right',     # 右转
        'move_forward',   # 右 1
        'move_forward',   # 右 2（达到限制）
        'look_right',     # 再右转（朝后）
        'move_forward',   # 后 1
        'move_forward',   # 后 2（达到限制）
        'look_right',     # 再右转（朝左）
        'move_forward',   # 左 1
        'move_forward',   # 左 2（达到限制）
        'move_forward',   # 左 3（应该失败）
        'move_up',        # 上 1
        'move_up',        # 上 2（应该失败，限制是1）
    ]
    
    for i, action in enumerate(actions, 1):
        success, reason = limiter.perform_action(action)
        status = limiter.get_status()
        
        print(f"\n动作 {i}: {action} - {'[成功]' if success else '[失败]'}")
        print(f"  朝向: {status['facing_name']}", end="")
        
        if action.startswith('move') and 'move_up' not in action and 'move_down' not in action:
            initial_dir = limiter.get_initial_direction(action)
            print(f" -> 初始方向: {initial_dir}", end="")
        
        if not success:
            print(f"\n  [警告] {reason}")
    
    print("\n\n最终状态:")
    print_status(limiter)


def test_up_movement_limit():
    """测试5: 向上移动限制"""
    print_separator("测试5: 向上移动限制")
    
    limiter = MovementLimiter(max_horizontal_moves=5, max_up_moves=2)
    
    actions = [
        'move_up',        # 上 1
        'move_forward',   # 前 1
        'move_up',        # 上 2（达到限制）
        'move_up',        # 上 3（应该失败）
        'look_right',     # 转向（不影响上下移动）
        'move_up',        # 仍然失败
        'move_down',      # 下移动（不限制）
    ]
    
    for i, action in enumerate(actions, 1):
        success, reason = limiter.perform_action(action)
        print(f"动作 {i}: {action} - {'[成功]' if success else '[失败]'}")
        if not success:
            print(f"  原因: {reason}")
    
    print("\n最终状态:")
    print_status(limiter)


def test_full_rotation():
    """测试6: 完整旋转一圈"""
    print_separator("测试6: 完整旋转一圈")
    
    limiter = MovementLimiter(max_horizontal_moves=10, max_up_moves=5)
    
    actions = [
        'move_forward',   # 前 1
        'look_right',     # 右转 (facing=1)
        'move_forward',   # 向右 1
        'look_right',     # 右转 (facing=2)
        'move_forward',   # 向后 1
        'look_right',     # 右转 (facing=3)
        'move_forward',   # 向左 1
        'look_right',     # 右转 (facing=0, 回到初始朝向)
        'move_forward',   # 前 2
    ]
    
    for i, action in enumerate(actions, 1):
        success, reason = limiter.perform_action(action)
        status = limiter.get_status()
        
        print(f"\n动作 {i}: {action}")
        print(f"  counter: {status['rotation_counter']}, 朝向: {status['facing_name']}")
        
        if action.startswith('move'):
            initial_dir = limiter.get_initial_direction(action)
            print(f"  初始方向: {initial_dir}")
    
    print("\n最终状态:")
    print_status(limiter)
    
    # 验证计数
    status = limiter.get_status()
    assert status['move_counts']['forward'] == 2
    assert status['move_counts']['right'] == 1
    assert status['move_counts']['backward'] == 1
    assert status['move_counts']['left'] == 1
    print("\n[验证通过] 完整旋转一圈后各方向计数正确")


if __name__ == "__main__":
    print("=" * 60)
    print("  MovementLimiter 测试套件")
    print("=" * 60)
    
    test_basic_movement()
    test_rotation_and_movement()
    test_negative_rotation()
    test_complex_scenario()
    test_up_movement_limit()
    test_full_rotation()
    
    print("\n" + "=" * 60)
    print("  所有测试完成！")
    print("=" * 60)

