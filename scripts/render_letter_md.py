import argparse, json, os


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--analysis', required=True)
    ap.add_argument('--out', required=True)
    args=ap.parse_args()

    with open(args.analysis,'r',encoding='utf-8') as f:
        d=json.load(f)

    cov=d['coverage']
    bills=d['bills_summary']

    insts=', '.join(cov.get('instIds') or [])

    # friend tone, minimal data
    txt = []
    txt.append('# 写给你的一封信')
    txt.append('')
    txt.append('我不想把这段交易写成报告。说白一点，我更像是把它当成一个人怎么和市场相处的记录，看了一遍。')
    txt.append('')
    txt.append(f"这段样本主要在：{insts if insts else '（无）'}。")
    txt.append('')
    txt.append('我并不觉得你不会交易。更像是：你会的那部分还没有被结构保护好。')
    txt.append('你手里有刀，但你有时候拿它去砍了不值得砍的波动，久了刀口会钝。')
    txt.append('')
    txt.append('你现在最需要的不是更多方法，而是更少的出手次数、更少的品种、更硬的边界。')
    txt.append('')
    txt.append('—— 小棠')

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out,'LETTER.md'),'w',encoding='utf-8') as f:
        f.write('\n'.join(txt) + '\n')

if __name__=='__main__':
    main()
