query = '三上悠亚, 苍井空, 波多野结衣'
print('原始查询字符串:', query)
parts = query.split(';')
print('按分号分割后的部分:', parts)
actress_names = []
for part in parts:
    sub_parts = part.split(',')
    print('按逗号分割后的部分:', sub_parts)
    for sp in sub_parts:
        actress_name = sp.strip()
        print('处理后的女优名字:', repr(actress_name))
        if actress_name:
            actress_names.append(actress_name)
print('最终的女优名字列表:', actress_names)
print('女优名字数量:', len(actress_names))
