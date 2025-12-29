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
    print(f"净移动统计 (相对于初始位置):")
    net = status['net_movements']
    limits = status['limits']
    
    # 前后方向
    fb_net = net['forward_backward']
    fb_sign = "前" if fb_net >= 0 else "后"
    print(f"  前后: {abs(fb_net)} ({fb_sign}) / 限制: {limits['horizontal']}")
    
    # 左右方向
    lr_net = net['left_right']
    lr_sign = "左" if lr_net >= 0 else "右"
    print(f"  左右: {abs(lr_net)} ({lr_sign}) / 限制: {limits['horizontal']}")
    
    # 上下方向
    ud_net = net['up_down']
    ud_sign = "上" if ud_net >= 0 else "下"
    print(f"  上下: {abs(ud_net)} ({ud_sign}) / 限制: {limits['up']}")
    
    print(f"总动作数: {status['total_actions']}")


def test_basic_movement():
    """测试1: 基本移动（不转向）- 测试净移动抵消"""
    print_separator("测试1: 基本移动（不转向）- 测试净移动抵消")
    
    limiter = MovementLimiter(max_horizontal_moves=2, max_up_moves=1)
    
    # 测试净移动抵消：向前2次(+2)，向后1次(-1)，再向前1次(+1)
    # 净移动 = +2-1+1 = +2，绝对值2 <= 限制2，应该允许
    actions = [
        'move_forward',   # 向前 +1，净移动: +1
        'move_forward',   # 向前 +1，净移动: +2
        'move_backward',  # 向后 -1，净移动: +1
        'move_forward',   # 向前 +1，净移动: +2（应该成功，因为abs(+2) <= 2）
        'move_forward',   # 向前 +1，净移动: +3（应该失败，因为abs(+3) > 2）
        'move_left',      # 向左 +1，净移动: +1
        'move_right',     # 向右 -1，净移动: 0（抵消）
        'move_left',      # 向左 +1，净移动: +1
        'move_left',      # 向左 +1，净移动: +2（应该成功）
        'move_left',      # 向左 +1，净移动: +3（应该失败）
    ]
    
    for i, action in enumerate(actions, 1):
        success, reason = limiter.perform_action(action)
        status = limiter.get_status()
        net = status['net_movements']
        print(f"\n动作 {i}: {action}")
        print(f"  结果: {'[成功]' if success else '[失败]'}")
        print(f"  原因: {reason}")
        print(f"  净移动 - 前后: {net['forward_backward']}, 左右: {net['left_right']}")
        if not success:
            print_status(limiter)
    
    print("\n最终状态:")
    print_status(limiter)


def test_rotation_and_movement():
    """测试2: 转向后的移动"""
    print_separator("测试2: 转向后的移动")
    
    limiter = MovementLimiter(max_horizontal_moves=3, max_up_moves=1)
    
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
        status = limiter.get_status()
        net = status['net_movements']
        print(f"\n动作 {i}: {action}")
        print(f"  结果: {'[成功]' if success else '[失败]'}")
        
        if action.startswith('move'):
            initial_dir = limiter.get_initial_direction(action)
            print(f"  当前朝向: {status['facing_name']}")
            print(f"  映射到初始方向: {initial_dir}")
            print(f"  净移动 - 前后: {net['forward_backward']}, 左右: {net['left_right']}")
        elif action.startswith('look'):
            print(f"  转向后朝向: {status['facing_name']}")
    
    print("\n最终状态:")
    print_status(limiter)


def test_negative_rotation():
    """测试3: 负数旋转（左转）"""
    print_separator("测试3: 负数旋转测试")
    
    limiter = MovementLimiter(max_horizontal_moves=3, max_up_moves=1)
    
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
        status = limiter.get_status()
        net = status['net_movements']
        print(f"\n动作 {i}: {action}")
        
        print(f"  rotation_counter: {status['rotation_counter']}")
        print(f"  当前朝向: {status['facing_name']} (facing={status['current_facing']})")
        
        if action.startswith('move'):
            initial_dir = limiter.get_initial_direction(action)
            print(f"  映射到初始方向: {initial_dir}")
            print(f"  净移动 - 前后: {net['forward_backward']}, 左右: {net['left_right']}")
    
    print("\n最终状态:")
    print_status(limiter)


def test_complex_scenario():
    """测试4: 复杂场景 - 多次转向和移动（测试净移动抵消）"""
    print_separator("测试4: 复杂场景 - 净移动抵消")
    
    limiter = MovementLimiter(max_horizontal_moves=2, max_up_moves=1)
    
    # 测试场景：净移动抵消
    # 前后方向：向前2次(+2)，向后1次(-1)，净移动=+1，再向前1次(+1)，净移动=+2（允许）
    # 左右方向：向右2次(-2)，向左1次(+1)，净移动=-1，再向左1次(+1)，净移动=0（允许）
    actions = [
        'move_forward',   # 前 +1，净移动: +1
        'move_forward',   # 前 +1，净移动: +2
        'look_right',     # 右转
        'move_forward',   # 右 -1，净移动: -1
        'move_forward',   # 右 -1，净移动: -2
        'look_right',     # 再右转（朝后）
        'move_forward',   # 后 -1，净移动: -1（前后方向净移动从+2变成+1）
        'move_forward',   # 后 -1，净移动: 0（前后方向净移动从+1变成0）
        'look_right',     # 再右转（朝左）
        'move_forward',   # 左 +1，净移动: +1
        'move_forward',   # 左 +1，净移动: 0（应该成功，abs(+2) <= 2）
        'move_forward',   # 左 +1，净移动: -1 （应该成功， abs(-1) <= 2）
        'move_up',        # 上 +1，净移动: +1
        'move_up',        # 上 +1，净移动: +2（应该失败，abs(+2) > 限制1）
    ]
    
    for i, action in enumerate(actions, 1):
        success, reason = limiter.perform_action(action)
        status = limiter.get_status()
        net = status['net_movements']
        
        print(f"\n动作 {i}: {action} - {'[成功]' if success else '[失败]'}")
        print(f"  朝向: {status['facing_name']}", end="")
        
        if action.startswith('move') and 'move_up' not in action and 'move_down' not in action:
            initial_dir = limiter.get_initial_direction(action)
            print(f" -> 初始方向: {initial_dir}", end="")
        
        print(f"\n  净移动 - 前后: {net['forward_backward']}, 左右: {net['left_right']}, 上下: {net['up_down']}")
        
        if not success:
            print(f"  [警告] {reason}")
    
    print("\n\n最终状态:")
    print_status(limiter)


def test_up_movement_limit():
    """测试5: 上下移动限制（净移动）"""
    print_separator("测试5: 上下移动限制（净移动）")
    
    limiter = MovementLimiter(max_horizontal_moves=5, max_up_moves=1)
    
    # 测试上下方向的净移动抵消（限制为1）
    actions = [
        'move_up',        # 上 +1，净移动: +1（达到限制）
        'move_forward',   # 前 +1（不影响上下）
        'move_up',        # 上 +1，净移动: +2（应该失败，abs(+2) > 1）
        'look_right',     # 转向（不影响上下移动）
        'move_up',        # 仍然失败
        'move_down',      # 下 -1，净移动: +2（允许）
        'move_down',      # 下 -1，净移动: +1（允许）
        'move_down',      # 下 -1，净移动: 0（（允许）
    ]
    
    for i, action in enumerate(actions, 1):
        success, reason = limiter.perform_action(action)
        status = limiter.get_status()
        net = status['net_movements']
        print(f"动作 {i}: {action} - {'[成功]' if success else '[失败]'}")
        print(f"  上下净移动: {net['up_down']}")
        if not success:
            print(f"  原因: {reason}")
    
    print("\n最终状态:")
    print_status(limiter)


def test_net_movement_cancellation():
    """测试6: 净移动抵消场景（用户示例）"""
    print_separator("测试6: 净移动抵消场景（用户示例）")
    
    limiter = MovementLimiter(max_horizontal_moves=2, max_up_moves=1)
    
    # 用户示例：限制为2，向前2次(+2)，向后1次(-1)，再向前1次(+1)
    # 净移动 = +2-1+1 = +2，绝对值2 <= 限制2，应该允许
    actions = [
        'move_forward',   # 向前 +1，净移动: +1
        'move_forward',   # 向前 +1，净移动: +2
        'move_backward',  # 向后 -1，净移动: +1
        'move_forward',   # 向前 +1，净移动: +2（应该成功，abs(+2) <= 2）
        'move_forward',   # 向前 +1，净移动: +3（应该失败，abs(+3) > 2）
    ]
    
    for i, action in enumerate(actions, 1):
        success, reason = limiter.perform_action(action)
        status = limiter.get_status()
        net = status['net_movements']
        
        print(f"\n动作 {i}: {action}")
        print(f"  结果: {'[成功]' if success else '[失败]'}")
        print(f"  前后净移动: {net['forward_backward']} (绝对值: {abs(net['forward_backward'])})")
        print(f"  原因: {reason}")
    
    print("\n最终状态:")
    print_status(limiter)
    
    # 验证最终净移动
    status = limiter.get_status()
    net = status['net_movements']
    assert net['forward_backward'] == 2, f"前后净移动应为2，实际为{net['forward_backward']}"
    print("\n[验证通过] 净移动抵消逻辑正确：向前2次，向后1次，再向前1次，净移动为+2，未超过限制")


def test_full_rotation():
    """测试6: 完整旋转一圈（测试净移动）"""
    print_separator("测试6: 完整旋转一圈（测试净移动）")
    
    limiter = MovementLimiter(max_horizontal_moves=10, max_up_moves=1)
    
    # 场景：向前1次(+1)，右转后向前1次(-1向右)，再右转向前1次(-1向后)，再右转向前1次(+1向左)，再右转向前1次(+1向前)
    # 前后净移动: +1-1-1+1+1 = +1
    # 左右净移动: -1+1 = 0
    actions = [
        'move_forward',   # 前 +1，前后净移动: +1
        'look_right',     # 右转 (facing=1)
        'move_forward',   # 右 -1，左右净移动: -1
        'look_right',     # 右转 (facing=2)
        'move_forward',   # 后 -1，前后净移动: 0
        'look_right',     # 右转 (facing=3)
        'move_forward',   # 左 +1，左右净移动: 0
        'look_right',     # 右转 (facing=0, 回到初始朝向)
        'move_forward',   # 前 +1，前后净移动: +1
    ]
    
    for i, action in enumerate(actions, 1):
        success, reason = limiter.perform_action(action)
        status = limiter.get_status()
        net = status['net_movements']
        
        print(f"\n动作 {i}: {action}")
        print(f"  counter: {status['rotation_counter']}, 朝向: {status['facing_name']}")
        
        if action.startswith('move'):
            initial_dir = limiter.get_initial_direction(action)
            print(f"  初始方向: {initial_dir}")
            print(f"  净移动 - 前后: {net['forward_backward']}, 左右: {net['left_right']}")
    
    print("\n最终状态:")
    print_status(limiter)
    
    # 验证净移动计数
    status = limiter.get_status()
    net = status['net_movements']
    assert net['forward_backward'] == 1, f"前后净移动应为1，实际为{net['forward_backward']}"
    assert net['left_right'] == 0, f"左右净移动应为0，实际为{net['left_right']}"
    print("\n[验证通过] 完整旋转一圈后净移动计数正确")


if __name__ == "__main__":
    print("=" * 60)
    print("  MovementLimiter 测试套件（净移动计数版本）")
    print("=" * 60)
    
    test_basic_movement()
    test_rotation_and_movement()
    test_negative_rotation()
    test_complex_scenario()
    test_up_movement_limit()
    test_net_movement_cancellation()
    test_full_rotation()
    
    print("\n" + "=" * 60)
    print("  所有测试完成！")
    print("=" * 60)

