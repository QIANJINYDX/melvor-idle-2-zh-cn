"""Keep the original currency and duration units requested by the user."""
UNITS = {
    'GP': 'GP', 'Gold Pieces': 'Gold Pieces', '/hr': '/hr',
    '{0:0.##}K': '{0:0.##}K', '{0:#,0.##}M': '{0:#,0.##}M',
    '{0:#,0.##}B': '{0:#,0.##}B', '{0:#,0.##}T': '{0:#,0.##}T',
    '+{0:0.##}s': '+{0:0.##}s', '{0:0.00}s': '{0:0.00}s',
    '{0:F2}s': '{0:F2}s', '{0:F2}s - {1:F2}s': '{0:F2}s - {1:F2}s',
    '0h': '0h', '4h 3s': '4h 3s', '69s (lol)': '69s (lol)',
    'Every 1h': '每1h', 'Every 24h': '每24h',
    'Eat in 6h': '6h后进食', 'Treat in 6h': '6h后吃零食',
    'Produce in 6h': '6h后产出', 'Dead in 8d': '8d后死亡',
    '> 999d until resource depleted': '资源耗尽还需>999d',
    '>999d until depleted': '耗尽还需>999d',
    '>999d until {0.DisplayName.Singular} depleted': '{0.DisplayName.Singular}耗尽还需>999d',
    '>999d until {0.DisplayName} depleted': '{0.DisplayName}耗尽还需>999d',
    '[b]>999d[/b] left to': '还需[b]>999d[/b]',
    'Lasts for {0:F2}s': '持续{0:F2}s',
    'Procs once every {0:F2}s': '每{0:F2}s触发一次',
    'Taking {0:N0} damage every {1:F2}s': '每{1:F2}s受到{0:N0}点伤害',
    'Within {0}s - {1:P0} chance': '{0}s内 - {1:P0}概率',
    '{0:N0} proc left. ({1:F2}s)': '剩余{0:N0}次触发。（{1:F2}s）',
    '{0:N0} procs left. ({1:F2}s)': '剩余{0:N0}次触发。（{1:F2}s）',
    '{0:N0} times, {1:N2}s': '{0:N0}次，{1:N2}s',
}


def preserve_units(source, translated):
    if source in UNITS:
        return UNITS[source]
    if 'GP' in source:
        return translated.replace('金币', 'GP')
    return translated
