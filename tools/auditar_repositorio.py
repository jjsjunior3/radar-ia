"""Auditoria local: detecta candidatos sem imprimir valores; nao altera Git."""
import argparse,json,re,subprocess
from pathlib import Path

PATTERNS={
 'aws_access_key':re.compile(r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
 'provider_key':re.compile(r'\bsk-(?:or-v1-|proj-)?[A-Za-z0-9_-]{24,}\b'),
 'github_token':re.compile(r'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
 'private_key':re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
 'jwt':re.compile(r'\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\b'),
}
WARNINGS={
 'aws_account_id':re.compile(r'\b\d{12}\b'),
 'personal_email':re.compile(r'[\w.+-]+@(gmail|hotmail|outlook|yahoo)\.[A-Za-z.]+'),
 'personal_path':re.compile(r'[A-Z]:[\\/]+Users[\\/]+[A-Za-z0-9_-]+'),
}


def findings(data,filename,revision=None):
    if b'\0' in data or len(data)>2_000_000:return []
    try:text=data.decode('utf-8-sig')
    except UnicodeDecodeError:return []
    result=[]
    for severity,patterns in [('blocker',PATTERNS),('review',WARNINGS)]:
        for name,pattern in patterns.items():
            for match in pattern.finditer(text):
                if name=='aws_account_id' and match.group() in ('123456789012','000000000000'):continue
                result.append({'severity':severity,'category':name,'file':filename,'line':text.count('\n',0,match.start())+1,**({'blob':revision} if revision else {})})
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--history',action='store_true');args=parser.parse_args()
    files=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard']).decode().split('\0')
    report={'working_tree':[],'history':[],'forbidden_files':[],'forbidden_history_files':[]}
    for name in sorted(set(files)-{''}):
        path=Path(name)
        if not path.is_file():continue
        if (path.name=='.env' or path.name.startswith('.env.') and path.name!='.env.example') or name.startswith(('.venv/','local-output/','.aws/')) or path.suffix.lower() in ('.wav','.mp3','.zip','.pem','.p12'):
            report['forbidden_files'].append(name)
        report['working_tree'].extend(findings(path.read_bytes(),name))
    if args.history:
        objects=subprocess.check_output(['git','rev-list','--objects','--all'],text=True).splitlines()
        for record in objects:
            identifier,separator,name=record.partition(' ')
            if not separator:continue
            path=Path(name)
            if (path.name=='.env' or path.name.startswith('.env.') and path.name!='.env.example') or name.startswith(('.venv/','local-output/','.aws/')) or path.suffix.lower() in ('.wav','.mp3','.zip','.pem','.key','.p12'):
                report['forbidden_history_files'].append({'file':name,'blob':identifier})
            raw=subprocess.check_output(['git','cat-file','-p',identifier])
            report['history'].extend(findings(raw,name,identifier))
    target=Path('local-output/auditoria-publicacao.json');target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
    for section in ('working_tree','history'):
        candidates=report[section]
        print(section+':',len(candidates),'candidatos; valores omitidos.')
        for item in candidates[:30]:print(item['severity'],item['category'],item['file']+':'+str(item['line']))
    print('Arquivos proibidos rastreados:',len(report['forbidden_files']),'| No historico:',len(report['forbidden_history_files']))
    print('Relatorio:',target.resolve())
    blockers=report['forbidden_files'] or report['forbidden_history_files'] or any(item['severity']=='blocker' for area in ('working_tree','history') for item in report[area])
    raise SystemExit(1 if blockers else 0)


if __name__=='__main__':main()
