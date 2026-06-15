# bot.py — iTzTasin69 CRYZON CLOUD ⚡ Ultra-Premium Edition
import discord
from discord.ext import commands
import asyncio
import subprocess
import json
from datetime import datetime
import shlex
import logging
import shutil
import os
from typing import Optional, List, Dict, Any
import threading
import time
import sqlite3
import random

# ──────────────────────────────────────────────
#  CONFIGURATION
# ──────────────────────────────────────────────
DISCORD_TOKEN      = os.getenv('DISCORD_TOKEN', 'MTUxNTYyNTA3MzYyMzQzNzM1Mw.GlzFbb.MQef_-vtPHMl6Di-rTFJYSlyT_TCu526ESQtos')
BOT_NAME           = os.getenv('BOT_NAME', 'CryzonCloud VPS Manager')
PREFIX             = os.getenv('PREFIX', 'cc!')
YOUR_SERVER_IP     = os.getenv('YOUR_SERVER_IP', '127.0.0.1')
MAIN_ADMIN_ID      = int(os.getenv('MAIN_ADMIN_ID', '1303298824382582784'))
DEFAULT_STORAGE_POOL = os.getenv('DEFAULT_STORAGE_POOL', 'default')

# ──────────────────────────────────────────────
#  OS OPTIONS
# ──────────────────────────────────────────────
OS_OPTIONS = [
    {"label": "Ubuntu 20.04 LTS",    "value": "ubuntu:20.04",      "emoji": "🟠"},
    {"label": "Ubuntu 22.04 LTS",    "value": "ubuntu:22.04",      "emoji": "🟠"},
    {"label": "Ubuntu 24.04 LTS",    "value": "ubuntu:24.04",      "emoji": "🟠"},
    {"label": "Debian 10 (Buster)",  "value": "images:debian/10",  "emoji": "🔴"},
    {"label": "Debian 11 (Bullseye)","value": "images:debian/11",  "emoji": "🔴"},
    {"label": "Debian 12 (Bookworm)","value": "images:debian/12",  "emoji": "🔴"},
    {"label": "Debian 13 (Trixie)",  "value": "images:debian/13",  "emoji": "🔴"},
]

# ──────────────────────────────────────────────
#  PREMIUM COLOUR PALETTE
# ──────────────────────────────────────────────
class Colors:
    PRIMARY    = 0x6C63FF
    SUCCESS    = 0x00E5A0
    ERROR      = 0xFF3366
    WARNING    = 0xFFB300
    INFO       = 0x00B4D8
    GOLD       = 0xFFD700
    DARK       = 0x0D1117
    MUTED      = 0x2B2D31
    RUNNING    = 0x00E5A0
    STOPPED    = 0xFFB300
    SUSPENDED  = 0xFF3366
    PURPLE     = 0xAB47BC
    TEAL       = 0x00BFA5
    PINK       = 0xF50057
    NAVY       = 0x1A237E
    LIME       = 0x76FF03

# ──────────────────────────────────────────────
#  DIRECTORIES — Create before logging
# ──────────────────────────────────────────────
os.makedirs('/opt/CryzonCloud/backups', exist_ok=True)

# ──────────────────────────────────────────────
#  LOGGING
# ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('/opt/CryzonCloud/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(f'{BOT_NAME.lower()}_bot')

# ──────────────────────────────────────────────
#  LXC CHECK
# ──────────────────────────────────────────────
if not shutil.which("lxc"):
    logger.error("LXC command not found. Please ensure LXC is installed.")
    raise SystemExit("LXC command not found.")

# ──────────────────────────────────────────────
#  DATABASE
# ──────────────────────────────────────────────
DB_PATH = '/opt/CryzonCloud/vps.db'

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS admins (user_id TEXT PRIMARY KEY)''')
    cur.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (str(MAIN_ADMIN_ID),))
    cur.execute('''CREATE TABLE IF NOT EXISTS vps (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        container_name TEXT UNIQUE NOT NULL,
        ram TEXT NOT NULL, cpu TEXT NOT NULL, storage TEXT NOT NULL,
        config TEXT NOT NULL, os_version TEXT DEFAULT 'ubuntu:22.04',
        status TEXT DEFAULT 'stopped', suspended INTEGER DEFAULT 0,
        whitelisted INTEGER DEFAULT 0, created_at TEXT NOT NULL,
        shared_with TEXT DEFAULT '[]', suspension_history TEXT DEFAULT '[]'
    )''')
    cur.execute('PRAGMA table_info(vps)')
    columns = [c[1] for c in cur.fetchall()]
    if 'os_version' not in columns:
        cur.execute("ALTER TABLE vps ADD COLUMN os_version TEXT DEFAULT 'ubuntu:22.04'")
    cur.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)''')
    for k, v in [('cpu_threshold','90'),('ram_threshold','90')]:
        cur.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)',(k,v))
    conn.commit(); conn.close()

def get_setting(key: str, default: Any = None):
    conn=get_db(); cur=conn.cursor()
    cur.execute('SELECT value FROM settings WHERE key=?',(key,))
    row=cur.fetchone(); conn.close()
    return row[0] if row else default

def set_setting(key: str, value: str):
    conn=get_db(); cur=conn.cursor()
    cur.execute('INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)',(key,value))
    conn.commit(); conn.close()

def get_vps_data() -> Dict[str,List[Dict]]:
    conn=get_db(); cur=conn.cursor()
    cur.execute('SELECT * FROM vps')
    rows=cur.fetchall(); conn.close()
    data={}
    for row in rows:
        uid=row['user_id']
        if uid not in data: data[uid]=[]
        vps=dict(row)
        vps['shared_with']=json.loads(vps['shared_with'])
        vps['suspension_history']=json.loads(vps['suspension_history'])
        vps['suspended']=bool(vps['suspended'])
        vps['whitelisted']=bool(vps['whitelisted'])
        vps['os_version']=vps.get('os_version','ubuntu:22.04')
        data[uid].append(vps)
    return data

def get_admins() -> List[str]:
    conn=get_db(); cur=conn.cursor()
    cur.execute('SELECT user_id FROM admins')
    rows=cur.fetchall(); conn.close()
    return [r['user_id'] for r in rows]

def save_vps_data():
    conn=get_db(); cur=conn.cursor()
    for uid, vlist in vps_data.items():
        for vps in vlist:
            sw=json.dumps(vps['shared_with'])
            sh=json.dumps(vps['suspension_history'])
            si=1 if vps['suspended'] else 0
            wi=1 if vps.get('whitelisted',False) else 0
            ov=vps.get('os_version','ubuntu:22.04')
            ca=vps.get('created_at',datetime.now().isoformat())
            if 'id' not in vps or vps['id'] is None:
                cur.execute('''INSERT INTO vps (user_id,container_name,ram,cpu,storage,config,os_version,status,suspended,whitelisted,created_at,shared_with,suspension_history)
                               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                            (uid,vps['container_name'],vps['ram'],vps['cpu'],vps['storage'],vps['config'],ov,vps['status'],si,wi,ca,sw,sh))
                vps['id']=cur.lastrowid
            else:
                cur.execute('''UPDATE vps SET user_id=?,ram=?,cpu=?,storage=?,config=?,os_version=?,status=?,suspended=?,whitelisted=?,shared_with=?,suspension_history=?
                               WHERE id=?''',
                            (uid,vps['ram'],vps['cpu'],vps['storage'],vps['config'],ov,vps['status'],si,wi,sw,sh,vps['id']))
    conn.commit(); conn.close()

def save_admin_data():
    conn=get_db(); cur=conn.cursor()
    cur.execute('DELETE FROM admins')
    for aid in admin_data['admins']:
        cur.execute('INSERT INTO admins(user_id) VALUES(?)',(aid,))
    conn.commit(); conn.close()

# ──────────────────────────────────────────────
#  INIT
# ──────────────────────────────────────────────
init_db()
vps_data   = get_vps_data()
admin_data = {'admins': get_admins()}
CPU_THRESHOLD = int(get_setting('cpu_threshold',90))
RAM_THRESHOLD = int(get_setting('ram_threshold',90))

# ──────────────────────────────────────────────
#  BOT SETUP
# ──────────────────────────────────────────────
intents                = discord.Intents.default()
intents.message_content = True
intents.members        = True
bot = commands.Bot(command_prefix=PREFIX, intents=intents, help_command=None)
resource_monitor_active = True

# ──────────────────────────────────────────────
#  PREMIUM EMBED BUILDER
# ──────────────────────────────────────────────
BOT_ICON  = "https://z-cdn-media.chatglm.cn/files/ada3a3cf-90a5-472d-bfec-95208faa91dc.png?auth_key=1881427706-fa353d81c7c1429ea5cd8d685995d908-0-3d87a478650d4efdd92ca7f2196ed730"

DIV   = "═" * 32
DASH  = "─" * 28

def _ts() -> str:
    return datetime.now().strftime('%d %b %Y  •  %H:%M UTC')

def truncate(text:str, limit:int=4096)->str:
    if not text: return text
    return text if len(text)<=limit else text[:limit-3]+"…"

def build_embed(title:str, description:str="", color:int=Colors.PRIMARY, thumbnail:bool=True) -> discord.Embed:
    embed = discord.Embed(title=truncate(f"{title}", 256), description=truncate(description, 4096), color=color)
    if thumbnail: embed.set_thumbnail(url=BOT_ICON)
    embed.set_footer(text=f"{BOT_NAME}  ⚡  by iTzTasin69  •  {_ts()}", icon_url=BOT_ICON)
    return embed

def field(embed:discord.Embed, name:str, value:str, inline:bool=False) -> discord.Embed:
    embed.add_field(name=truncate(name, 256), value=truncate(value, 1024), inline=inline)
    return embed

def success_embed(title:str, desc:str="") -> discord.Embed: return build_embed(f"✅  {title}", desc, Colors.SUCCESS)
def error_embed(title:str, desc:str="") -> discord.Embed: return build_embed(f"❌  {title}", desc, Colors.ERROR)
def info_embed(title:str, desc:str="") -> discord.Embed: return build_embed(f"💡  {title}", desc, Colors.INFO)
def warn_embed(title:str, desc:str="") -> discord.Embed: return build_embed(f"⚠️  {title}", desc, Colors.WARNING)
def gold_embed(title:str, desc:str="") -> discord.Embed: return build_embed(f"👑  {title}", desc, Colors.GOLD)

def status_badge(vps:dict) -> str:
    s = vps.get('status','unknown'); sus = vps.get('suspended',False); wl = vps.get('whitelisted',False)
    if sus: badge = "🔒 `SUSPENDED`"
    elif s == 'running': badge = "🟢 `RUNNING`"
    elif s == 'stopped': badge = "🔴 `STOPPED`"
    else: badge = f"⚪ `{s.upper()}`"
    if wl: badge += "  🛡️ `WHITELISTED`"
    return badge

def status_color(vps:dict) -> int:
    if vps.get('suspended'): return Colors.SUSPENDED
    s = vps.get('status','unknown')
    return Colors.RUNNING if s=='running' else Colors.STOPPED if s=='stopped' else Colors.MUTED

def progress_bar(pct:float, width:int=12) -> str:
    pct = max(0.0, min(100.0, pct)); filled = int(pct / 100 * width); bar = "█" * filled + "░" * (width - filled)
    dot = "🟢" if pct < 50 else "🟡" if pct < 80 else "🔴"
    return f"{dot} `{bar}` **{pct:.1f}%**"

def mini_bar(done:int, total:int, width:int=14) -> str:
    filled = round(width * done / total) if total else 0; pct = round(100 * done / total) if total else 0
    bar = "▰" * filled + "▱" * (width - filled)
    return f"`{bar}` **{pct}%**"

def step_list(steps:list, current:int) -> str:
    lines = []
    for i, (name, _) in enumerate(steps):
        if i < current: lines.append(f"  ✅  ~~{name}~~")
        elif i == current: lines.append(f"  ⚙️  **{name}**")
        else: lines.append(f"  ⬜  {name}")
    return "\n".join(lines)

def done_steps(steps:list) -> str:
    return "\n".join(f"  ✅  ~~{name}~~" for name, _ in steps)

def is_admin():
    async def predicate(ctx):
        uid=str(ctx.author.id)
        if uid==str(MAIN_ADMIN_ID) or uid in admin_data.get("admins",[]): return True
        raise commands.CheckFailure("🔒 You need **Admin** permission to use this command.")
    return commands.check(predicate)

def is_main_admin():
    async def predicate(ctx):
        if str(ctx.author.id)==str(MAIN_ADMIN_ID): return True
        raise commands.CheckFailure("👑 Only the **Main Admin** can use this command.")
    return commands.check(predicate)

async def execute_lxc(command:str, timeout:int=120):
    try:
        cmd=shlex.split(command)
        proc=await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try: stdout,stderr=await asyncio.wait_for(proc.communicate(),timeout=timeout)
        except asyncio.TimeoutError: proc.kill(); await proc.wait(); raise asyncio.TimeoutError(f"Command timed out after {timeout}s")
        if proc.returncode!=0: err=stderr.decode().strip() if stderr else "Command failed"; raise Exception(err)
        return stdout.decode().strip() if stdout else True
    except asyncio.TimeoutError as te: logger.error(f"LXC timeout: {command} — {te}"); raise
    except Exception as e: logger.error(f"LXC Error: {command} — {e}"); raise

async def apply_lxc_config(container:str):
    try:
        await execute_lxc(f"lxc config set {container} security.nesting true")
        await execute_lxc(f"lxc config set {container} security.privileged true")
        await execute_lxc(f"lxc config set {container} security.syscalls.intercept.mknod true")
        await execute_lxc(f"lxc config set {container} security.syscalls.intercept.setxattr true")
        try: await execute_lxc(f"lxc config device add {container} fuse unix-char path=/dev/fuse")
        except Exception as e:
            if "already exists" not in str(e).lower(): raise
        await execute_lxc(f"lxc config set {container} linux.kernel_modules overlay,loop,nf_nat,ip_tables,ip6_tables,netlink_diag,br_netfilter")
        raw="""lxc.apparmor.profile = unconfined\nlxc.cgroup.devices.allow = a\nlxc.cap.drop =\nlxc.mount.auto = proc:rw sys:rw cgroup:rw\n"""
        await execute_lxc(f"lxc config set {container} raw.lxc '{raw}'")
    except Exception as e: logger.error(f"LXC config failed for {container}: {e}")

async def apply_internal_permissions(container:str):
    try:
        await asyncio.sleep(5)
        cmds=["mkdir -p /etc/sysctl.d/","echo 'net.ipv4.ip_unprivileged_port_start=0' > /etc/sysctl.d/99-custom.conf","echo 'net.ipv4.ping_group_range=0 2147483647' >> /etc/sysctl.d/99-custom.conf","echo 'fs.inotify.max_user_watches=524288' >> /etc/sysctl.d/99-custom.conf","sysctl -p /etc/sysctl.d/99-custom.conf || true"]
        for cmd in cmds:
            try: await execute_lxc(f'lxc exec {container} -- bash -c "{cmd}"')
            except Exception as e: logger.warning(f"Internal perm cmd failed in {container}: {cmd} — {e}")
    except Exception as e: logger.error(f"Internal permissions failed for {container}: {e}")

async def get_or_create_vps_role(guild:discord.Guild):
    role=discord.utils.get(guild.roles,name="CryzonCloud VPS User")
    if role: return role
    try:
        role=await guild.create_role(name="CryzonCloud VPS User",color=discord.Color.from_rgb(108,99,255),reason="CryzonCloud VPS User cosmetic role",permissions=discord.Permissions.none())
        return role
    except Exception as e: logger.error(f"Failed to create VPS role: {e}"); return None

def get_cpu_usage()->float:
    try:
        if shutil.which("mpstat"):
            r=subprocess.run(['mpstat','1','1'],capture_output=True,text=True)
            for line in r.stdout.split('\n'):
                if 'all' in line and '%' in line: return 100.0-float(line.split()[-1])
        else:
            r=subprocess.run(['top','-bn1'],capture_output=True,text=True)
            for line in r.stdout.split('\n'):
                if '%Cpu(s):' in line: p=line.split(); return float(p[1])+float(p[3])+float(p[5])+float(p[9])+float(p[11])+float(p[13])+float(p[15])
        return 0.0
    except: return 0.0

def get_ram_usage()->float:
    try:
        r=subprocess.run(['free','-m'],capture_output=True,text=True)
        lines=r.stdout.splitlines()
        if len(lines)>1: m=lines[1].split(); return (int(m[2])/int(m[1])*100) if int(m[1])>0 else 0.0
        return 0.0
    except: return 0.0

def get_uptime()->str:
    try: r=subprocess.run(['uptime'],capture_output=True,text=True); return r.stdout.strip()
    except: return "Unknown"

def resource_monitor():
    global resource_monitor_active; backup_interval=3600; last_backup=time.time()
    while resource_monitor_active:
        try:
            cpu=get_cpu_usage(); ram=get_ram_usage()
            if cpu>CPU_THRESHOLD or ram>RAM_THRESHOLD: logger.warning(f"Thresholds exceeded — CPU:{cpu:.1f}% RAM:{ram:.1f}%")
            if time.time()-last_backup>backup_interval:
                bn=f"/opt/CryzonCloud/backups/vps_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
                try: shutil.copy(DB_PATH,bn); last_backup=time.time()
                except Exception as e: logger.error(f"Backup failed: {e}")
            time.sleep(60)
        except Exception as e: logger.error(f"Monitor error: {e}"); time.sleep(60)

monitor_thread=threading.Thread(target=resource_monitor,daemon=True); monitor_thread.start()

async def get_container_status(name:str)->str:
    try:
        proc=await asyncio.create_subprocess_exec("lxc","info",name,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout,_=await proc.communicate()
        for line in stdout.decode().splitlines():
            if line.startswith("Status: "): return line.split(": ",1)[1].strip().lower()
        return "unknown"
    except: return "unknown"

async def get_container_cpu_pct(name:str)->float:
    try:
        proc=await asyncio.create_subprocess_exec("lxc","exec",name,"--","bash","-c","cat /sys/fs/cgroup/cpu.stat 2>/dev/null || cat /sys/fs/cgroup/cpu/cpuacct.usage 2>/dev/null",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout,_=await proc.communicate(); text=stdout.decode().strip()
        for line in text.splitlines():
            if line.startswith("usage_usec"):
                usage1=int(line.split()[1]); await asyncio.sleep(0.5)
                proc2=await asyncio.create_subprocess_exec("lxc","exec",name,"--","bash","-c","cat /sys/fs/cgroup/cpu.stat",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
                stdout2,_=await proc2.communicate()
                for l2 in stdout2.decode().splitlines():
                    if l2.startswith("usage_usec"):
                        usage2=int(l2.split()[1]); delta_us=(usage2-usage1)
                        proc3=await asyncio.create_subprocess_exec("lxc","exec",name,"--","bash","-c","nproc 2>/dev/null || echo 1",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
                        s3,_=await proc3.communicate(); ncpu=max(1,int(s3.decode().strip() or 1))
                        return round(min((delta_us/(500000.0*ncpu))*100.0,100.0),1)
        if text.isdigit():
            usage1=int(text); await asyncio.sleep(0.5)
            proc2=await asyncio.create_subprocess_exec("lxc","exec",name,"--","bash","-c","cat /sys/fs/cgroup/cpu/cpuacct.usage",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            stdout2,_=await proc2.communicate(); usage2=int(stdout2.decode().strip()); delta_ns=usage2-usage1
            proc3=await asyncio.create_subprocess_exec("lxc","exec",name,"--","bash","-c","nproc 2>/dev/null || echo 1",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            s3,_=await proc3.communicate(); ncpu=max(1,int(s3.decode().strip() or 1))
            return round(min((delta_ns/(500000000.0*ncpu))*100.0,100.0),1)
        return 0.0
    except: return 0.0

async def get_container_cpu(name:str)->str: return f"{await get_container_cpu_pct(name):.1f}%"

async def _get_container_ram_bytes(name:str):
    try:
        proc=await asyncio.create_subprocess_exec("lxc","exec",name,"--","bash","-c","cat /sys/fs/cgroup/memory.current 2>/dev/null && echo '---' && cat /sys/fs/cgroup/memory.max 2>/dev/null || cat /sys/fs/cgroup/memory/memory.usage_in_bytes 2>/dev/null && echo '---' && cat /sys/fs/cgroup/memory/memory.limit_in_bytes 2>/dev/null",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout,_=await proc.communicate(); parts=[l.strip() for l in stdout.decode().split('---') if l.strip()]
        if len(parts)>=2:
            used=int(parts[0]); lim_raw=parts[1]
            if lim_raw in ('max','9223372036854771712',''):
                proc2=await asyncio.create_subprocess_exec("lxc","exec",name,"--","free","-b",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
                s2,_=await proc2.communicate(); lines=s2.decode().splitlines()
                lim=int(lines[1].split()[1]) if len(lines)>1 else used
            else: lim=int(lim_raw)
            return used,lim
    except: pass
    try:
        proc=await asyncio.create_subprocess_exec("lxc","exec",name,"--","free","-b",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout,_=await proc.communicate(); lines=stdout.decode().splitlines()
        if len(lines)>1: p=lines[1].split(); return int(p[2]),int(p[1])
    except: pass
    return 0,0

async def get_container_memory(name:str)->str:
    try:
        used,lim=await _get_container_ram_bytes(name)
        if lim==0: return "Unknown"
        return f"{used//1048576}/{lim//1048576} MB ({(used/lim*100):.1f}%)"
    except: return "Unknown"

async def get_container_ram_pct(name:str)->float:
    try: used,lim=await _get_container_ram_bytes(name); return round((used/lim*100),1) if lim>0 else 0.0
    except: return 0.0

async def get_container_disk(name:str)->str:
    try:
        proc=await asyncio.create_subprocess_exec("lxc","exec",name,"--","df","-h","/",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout,_=await proc.communicate(); lines=stdout.decode().splitlines()
        for line in reversed(lines):
            p=line.split()
            if len(p)>=6 and p[5]=='/': return f"{p[2]}/{p[1]} ({p[4]})"
        if len(lines)>1: p=lines[1].split(); return f"{p[2]}/{p[1]} ({p[4]})" if len(p)>=5 else "Unknown"
        return "Unknown"
    except: return "Unknown"

async def get_container_uptime(name:str)->str:
    try:
        proc=await asyncio.create_subprocess_exec("lxc","exec",name,"--","uptime",stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        stdout,_=await proc.communicate(); return stdout.decode().strip() if stdout else "Unknown"
    except: return "Unknown"

# ══════════════════════════════════════════════
#  BOT EVENTS
# ══════════════════════════════════════════════
@bot.event
async def on_ready():
    logger.info(f'{bot.user} is online!')
    total_vps = sum(len(v) for v in vps_data.values())
    running   = sum(1 for vl in vps_data.values() for v in vl if v.get('status')=='running' and not v.get('suspended'))
    await bot.change_presence(status=discord.Status.online,activity=discord.Activity(type=discord.ActivityType.watching,name=f"⚡ CryzonCloud | {running}/{total_vps} VPS Online"))
    logger.info(f"⚡ {BOT_NAME} by iTzTasin69 is ready!")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound): return
    elif isinstance(error, commands.MissingRequiredArgument): await ctx.send(embed=error_embed("Missing Argument",f"```\n{PREFIX}help\n```"))
    elif isinstance(error, commands.BadArgument): await ctx.send(embed=error_embed("Invalid Argument","Double-check your input."))
    elif isinstance(error, commands.CheckFailure): await ctx.send(embed=error_embed("Access Denied",str(error) if str(error) else "No permission."))
    else: logger.error(f"Command error: {error}"); await ctx.send(embed=error_embed("Error","Something went wrong."))

@bot.command(name='ping')
async def ping(ctx):
    lat = round(bot.latency * 1000)
    await ctx.send(embed=success_embed("Pong!  🏓",f"**⚡ Gateway Latency**\n{progress_bar(min(lat / 5, 100))}\n› `{lat} ms`"))

@bot.command(name='uptime')
async def uptime_cmd(ctx):
    embed = info_embed("Host System Uptime",f"```\n{get_uptime()}\n```")
    field(embed, "🖥️  Host CPU", progress_bar(get_cpu_usage()), True)
    field(embed, "🧠  Host RAM", progress_bar(get_ram_usage()), True)
    await ctx.send(embed=embed)

@bot.command(name='thresholds')
@is_admin()
async def thresholds(ctx):
    embed = info_embed("Resource Alert Thresholds",f"VPS flagged when exceeding limits.\n{DIV}")
    field(embed, "🖥️  CPU", f"{progress_bar(CPU_THRESHOLD)}\n› `{CPU_THRESHOLD}%`", True)
    field(embed, "🧠  RAM", f"{progress_bar(RAM_THRESHOLD)}\n› `{RAM_THRESHOLD}%`", True)
    await ctx.send(embed=embed)

@bot.command(name='set-threshold')
@is_admin()
async def set_threshold(ctx, cpu:int, ram:int):
    global CPU_THRESHOLD, RAM_THRESHOLD
    if cpu<0 or ram<0: await ctx.send(embed=error_embed("Invalid","Must be non-negative.")); return
    CPU_THRESHOLD=cpu; RAM_THRESHOLD=ram; set_setting('cpu_threshold',str(cpu)); set_setting('ram_threshold',str(ram))
    await ctx.send(embed=success_embed("Thresholds Updated",f"🖥️ CPU: `{cpu}%` | 🧠 RAM: `{ram}%`"))

@bot.command(name='set-status')
@is_admin()
async def set_status(ctx, activity_type:str, *, name:str):
    types={'playing':discord.ActivityType.playing,'watching':discord.ActivityType.watching,'listening':discord.ActivityType.listening,'streaming':discord.ActivityType.streaming}
    if activity_type.lower() not in types: await ctx.send(embed=error_embed("Invalid Type","playing/watching/listening/streaming")); return
    await bot.change_presence(activity=discord.Activity(type=types[activity_type.lower()],name=name))
    await ctx.send(embed=success_embed("Status Updated",f"› **{activity_type.title()}** `{name}`"))

@bot.command(name='myvps')
async def my_vps(ctx):
    uid=str(ctx.author.id); vlist=vps_data.get(uid,[])
    if not vlist: await ctx.send(embed=error_embed("No VPS Found",f"Use `{PREFIX}help` to explore.")); return
    run_count=sum(1 for v in vlist if v.get('status')=='running' and not v.get('suspended')); sus_count=sum(1 for v in vlist if v.get('suspended')); stop_count=len(vlist)-run_count-sus_count
    embed=info_embed(f"{ctx.author.display_name}'s VPS Fleet",f"You have **{len(vlist)}** VPS instance(s).\n{DIV}\n🟢 `{run_count}` Running  ·  🔴 `{stop_count}` Stopped  ·  🔒 `{sus_count}` Suspended")
    field(embed,"📊  Fleet Health",progress_bar(run_count/len(vlist)*100),False)
    for i,vps in enumerate(vlist,1): field(embed,f"🖥️  VPS #{i}",f"{status_badge(vps)}\n› **Container:** `{vps['container_name']}`\n› **Config:** {vps.get('config','Custom')}\n› **OS:** `{vps.get('os_version','N/A')}`",True)
    field(embed,"🎮  Management",f"`{PREFIX}manage` — Open VPS control panel",False)
    await ctx.send(embed=embed)

@bot.command(name='lxc-list')
@is_admin()
async def lxc_list(ctx):
    try:
        result=await execute_lxc("lxc list"); total=sum(len(v) for v in vps_data.values()); run=sum(1 for vl in vps_data.values() for v in vl if v.get('status')=='running' and not v.get('suspended'))
        embed=info_embed("LXC Container Registry",f"```\n{result}\n```")
        field(embed,"📊  Running",f"› `{run}` / `{total}` running",False); await ctx.send(embed=embed)
    except Exception as e: await ctx.send(embed=error_embed("LXC Error",str(e)))

class OSSelectView(discord.ui.View):
    def __init__(self, ram:int, cpu:int, disk:int, user:discord.Member, ctx):
        super().__init__(timeout=300); self.ram=ram; self.cpu=cpu; self.disk=disk; self.user=user; self.ctx=ctx
        self.select=discord.ui.Select(placeholder="🖥️  Choose an OS…",options=[discord.SelectOption(label=o["label"],value=o["value"],emoji=o.get("emoji")) for o in OS_OPTIONS])
        self.select.callback=self.select_os; self.add_item(self.select)

    async def select_os(self, interaction:discord.Interaction):
        if str(interaction.user.id)!=str(self.ctx.author.id): await interaction.response.send_message(embed=error_embed("Denied","Not your command."),ephemeral=True); return
        os_version=self.select.values[0]; self.select.disabled=True
        STEPS=[("Initializing container","lxc init"),("Allocating resources","limits"),("Configuring disk","disk"),("Applying security config","security"),("Booting container","start"),("Applying permissions","permissions"),("Finalizing","saving")]
        TOTAL=len(STEPS)
        def progress_embed(step_idx:int) -> discord.Embed:
            return build_embed("⚡  Provisioning VPS",f"**Owner:** {self.user.mention}  ·  **OS:** `{os_version}`\n**Resources:** `{self.ram}GB RAM`  ·  `{self.cpu} vCPU`  ·  `{self.disk}GB Disk`\n\n{mini_bar(step_idx, TOTAL)}\n\n{step_list(STEPS, step_idx)}",Colors.SUCCESS if round(100*step_idx/TOTAL)==100 else Colors.INFO)
        await interaction.response.edit_message(embed=progress_embed(0),view=self)
        async def update(step_idx:int):
            try: await interaction.edit_original_response(embed=progress_embed(step_idx))
            except: pass
        uid=str(self.user.id); vps_data.setdefault(uid,[]); count=len(vps_data[uid])+1; container=f"cryn-vps-{uid}-{count}"; ram_mb=self.ram*1024
        try:
            await execute_lxc(f"lxc init {os_version} {container} -s {DEFAULT_STORAGE_POOL}"); await update(1)
            await execute_lxc(f"lxc config set {container} limits.memory {ram_mb}MB"); await execute_lxc(f"lxc config set {container} limits.cpu {self.cpu}"); await update(2)
            try: await execute_lxc(f"lxc config device add {container} root disk pool={DEFAULT_STORAGE_POOL} path=/ size={self.disk}GB")
            except Exception as e:
                if "already exists" in str(e).lower(): await execute_lxc(f"lxc config device set {container} root size={self.disk}GB")
                else: raise
            await update(3); await apply_lxc_config(container); await update(4); await execute_lxc(f"lxc start {container}"); await update(5); await apply_internal_permissions(container); await update(6)
            cfg=f"{self.ram}GB RAM / {self.cpu} vCPU / {self.disk}GB Disk"
            info={"container_name":container,"ram":f"{self.ram}GB","cpu":str(self.cpu),"storage":f"{self.disk}GB","config":cfg,"os_version":os_version,"status":"running","suspended":False,"whitelisted":False,"suspension_history":[],"created_at":datetime.now().isoformat(),"shared_with":[],"id":None}
            vps_data[uid].append(info); save_vps_data()
            if self.ctx.guild:
                role=await get_or_create_vps_role(self.ctx.guild)
                if role:
                    try: await self.user.add_roles(role,reason=f"{BOT_NAME} VPS granted")
                    except: pass
            try: await interaction.edit_original_response(embed=build_embed("⚡  Provisioning VPS",f"**Owner:** {self.user.mention}\n\n{mini_bar(TOTAL, TOTAL)}\n\n{done_steps(STEPS)}",Colors.SUCCESS),view=self)
            except: pass
            embed=build_embed("🎉  VPS Deployed Successfully!","",Colors.SUCCESS)
            field(embed,"👤  Owner",self.user.mention,True); field(embed,"🔢  VPS",f"**#{count}**",True); field(embed,"📦  Container",f"`{container}`",True)
            field(embed,"💾  Resources",f"› RAM: `{self.ram}GB`\n› CPU: `{self.cpu} vCPU`\n› Disk: `{self.disk}GB`",True); field(embed,"🐧  OS",f"`{os_version}`",True)
            await interaction.followup.send(embed=embed)
            try:
                dm=build_embed("🚀  Your New VPS is Ready!","",Colors.SUCCESS)
                field(dm,"📦  Container",f"`{container}`",True); field(dm,"💾  Config",f"› RAM: `{self.ram}GB`\n› CPU: `{self.cpu} vCPU`\n› Disk: `{self.disk}GB`\n› OS: `{os_version}`",False)
                await self.user.send(embed=dm)
            except: pass
        except Exception as e: await interaction.followup.send(embed=error_embed("Provisioning Failed",f"```\n{str(e)}\n```"))

@bot.command(name='create')
@is_admin()
async def create_vps(ctx, ram:int, cpu:int, disk:int, user:discord.Member):
    if ram<=0 or cpu<=0 or disk<=0: await ctx.send(embed=error_embed("Invalid Specs","Must be positive.")); return
    embed=info_embed("VPS Provisioning Wizard",f"Configure VPS for {user.mention}.\n{DIV}\n**💾 RAM:** `{ram}GB`\n**⚙️ CPU:** `{cpu} vCPU`\n**🗄️ Disk:** `{disk}GB`\n\n*Select an OS below.*")
    await ctx.send(embed=embed,view=OSSelectView(ram,cpu,disk,user,ctx))

class ReinstallOSSelectView(discord.ui.View):
    def __init__(self, parent_view, container:str, owner_id:str, actual_idx:int, ram_gb:int, cpu:int, storage_gb:int):
        super().__init__(timeout=300); self.parent_view=parent_view; self.container=container; self.owner_id=owner_id; self.actual_idx=actual_idx; self.ram_gb=ram_gb; self.cpu=cpu; self.storage_gb=storage_gb
        self.select=discord.ui.Select(placeholder="🔄  Select New OS…",options=[discord.SelectOption(label=o["label"],value=o["value"],emoji=o.get("emoji")) for o in OS_OPTIONS])
        self.select.callback=self.select_os; self.add_item(self.select)

    async def select_os(self, interaction:discord.Interaction):
        os_version=self.select.values[0]; self.select.disabled=True
        await interaction.response.edit_message(embed=info_embed("Reinstalling…",f"**Container:** `{self.container}`\n**New OS:** `{os_version}`\n\n⏳ *Please wait…*"),view=self)
        ram_mb=self.ram_gb*1024
        try:
            try: await execute_lxc(f"lxc stop {self.container} --force")
            except: pass
            await execute_lxc(f"lxc delete {self.container} --force")
            await execute_lxc(f"lxc init {os_version} {self.container} -s {DEFAULT_STORAGE_POOL}")
            await execute_lxc(f"lxc config set {self.container} limits.memory {ram_mb}MB"); await execute_lxc(f"lxc config set {self.container} limits.cpu {self.cpu}")
            try: await execute_lxc(f"lxc config device add {self.container} root disk pool={DEFAULT_STORAGE_POOL} path=/ size={self.storage_gb}GB")
            except Exception as e:
                if "already exists" in str(e).lower(): await execute_lxc(f"lxc config device set {self.container} root size={self.storage_gb}GB")
                else: raise
            await apply_lxc_config(self.container); await execute_lxc(f"lxc start {self.container}"); await apply_internal_permissions(self.container)
            if self.owner_id in vps_data:
                for vps in vps_data[self.owner_id]:
                    if vps.get('container_name')==self.container: vps['os_version']=os_version; vps['status']='running'; vps['suspended']=False; break
                save_vps_data()
            await interaction.edit_original_response(embed=success_embed("VPS Reinstalled!",f"**Container:** `{self.container}`\n**New OS:** `{os_version}`\n**Status:** 🟢 Running"),view=self)
        except Exception as e: await interaction.edit_original_response(embed=error_embed("Reinstall Failed",f"```\n{str(e)}\n```"),view=self)

class VPSManageView(discord.ui.View):
    def __init__(self, ctx, user_id:str, vps_index:int):
        super().__init__(timeout=300); self.ctx=ctx; self.user_id=user_id; self.vps_index=vps_index

    def get_vps(self):
        vlist=vps_data.get(self.user_id,[])
        return vlist[self.vps_index] if self.vps_index<len(vlist) else None

    async def interaction_check(self, interaction:discord.Interaction) -> bool:
        return str(interaction.user.id)==self.user_id or str(interaction.user.id) in admin_data.get("admins",[])

    def build_manage_embed(self, vps:dict, status:str="unknown") -> discord.Embed:
        embed=build_embed("🎮  VPS Control Panel","",status_color(vps))
        field(embed,"📦  Container",f"`{vps['container_name']}`",True); field(embed,"📊  Status",status_badge(vps),True); field(embed,"💾  Config",vps.get('config','Custom'),True)
        field(embed,"🐧  OS",f"`{vps.get('os_version','N/A')}`",True); field(embed,"📅  Created",f"`{vps.get('created_at','N/A')[:16]}`",True)
        return embed

    @discord.ui.button(label="▶ Start", style=discord.ButtonStyle.success, row=0)
    async def start_btn(self, interaction:discord.Interaction, button:discord.ui.Button):
        vps=self.get_vps();
        if not vps: return
        if vps.get('suspended'): await interaction.response.send_message(embed=error_embed("Suspended","Cannot start."),ephemeral=True); return
        try:
            await execute_lxc(f"lxc start {vps['container_name']}"); vps['status']='running'; save_vps_data()
            await interaction.response.edit_message(embed=self.build_manage_embed(vps,'running'),view=self)
        except Exception as e: await interaction.response.send_message(embed=error_embed("Failed",str(e)),ephemeral=True)

    @discord.ui.button(label="⏹ Stop", style=discord.ButtonStyle.danger, row=0)
    async def stop_btn(self, interaction:discord.Interaction, button:discord.ui.Button):
        vps=self.get_vps();
        if not vps: return
        try:
            await execute_lxc(f"lxc stop {vps['container_name']}"); vps['status']='stopped'; save_vps_data()
            await interaction.response.edit_message(embed=self.build_manage_embed(vps,'stopped'),view=self)
        except Exception as e: await interaction.response.send_message(embed=error_embed("Failed",str(e)),ephemeral=True)

    @discord.ui.button(label="🔄 Restart", style=discord.ButtonStyle.primary, row=0)
    async def restart_btn(self, interaction:discord.Interaction, button:discord.ui.Button):
        vps=self.get_vps();
        if not vps: return
        try:
            await execute_lxc(f"lxc restart {vps['container_name']}"); vps['status']='running'; save_vps_data()
            await interaction.response.edit_message(embed=self.build_manage_embed(vps,'running'),view=self)
        except Exception as e: await interaction.response.send_message(embed=error_embed("Failed",str(e)),ephemeral=True)

    @discord.ui.button(label="📊 Stats", style=discord.ButtonStyle.secondary, row=1)
    async def stats_btn(self, interaction:discord.Interaction, button:discord.ui.Button):
        vps=self.get_vps();
        if not vps: return
        c=vps['container_name']
        try:
            cpu_pct=await get_container_cpu_pct(c); ram_pct=await get_container_ram_pct(c); mem_str=await get_container_memory(c); disk_str=await get_container_disk(c); up_str=await get_container_uptime(c)
            embed=info_embed(f"📊  Stats — {c}","")
            field(embed,"🖥️  CPU",f"{progress_bar(cpu_pct)}\n› `{cpu_pct:.1f}%`",True); field(embed,"🧠  RAM",f"{progress_bar(ram_pct)}\n› {mem_str}",True); field(embed,"🗄️  Disk",f"› {disk_str}",True); field(embed,"⏱️  Uptime",f"```\n{up_str}\n```",False)
            await interaction.response.send_message(embed=embed,ephemeral=True)
        except Exception as e: await interaction.response.send_message(embed=error_embed("Error",str(e)),ephemeral=True)

    @discord.ui.button(label="🔄 Reinstall", style=discord.ButtonStyle.secondary, row=1)
    async def reinstall_btn(self, interaction:discord.Interaction, button:discord.ui.Button):
        vps=self.get_vps();
        if not vps: return
        ram_val=int(vps['ram'].replace('GB','')); cpu_val=int(vps['cpu']); storage_val=int(vps['storage'].replace('GB',''))
        view=ReinstallOSSelectView(self,vps['container_name'],self.user_id,self.vps_index,ram_val,cpu_val,storage_val)
        await interaction.response.edit_message(embed=warn_embed("🔄  Reinstall VPS",f"**Container:** `{vps['container_name']}`\n\n⚠️ **All data will be wiped.** Select new OS below."),view=view)

    @discord.ui.button(label="🗑️ Delete", style=discord.ButtonStyle.danger, row=2)
    async def delete_btn(self, interaction:discord.Interaction, button:discord.ui.Button):
        vps=self.get_vps();
        if not vps: return
        class ConfirmDeleteView(discord.ui.View):
            def __init__(self, uid, idx, cont): super().__init__(timeout=60); self.uid=uid; self.idx=idx; self.cont=cont
            @discord.ui.button(label="✅ Confirm Delete", style=discord.ButtonStyle.danger)
            async def confirm(self, interaction:discord.Interaction, button:discord.ui.Button):
                try:
                    try: await execute_lxc(f"lxc stop {self.cont} --force")
                    except: pass
                    await execute_lxc(f"lxc delete {self.cont} --force")
                    if self.uid in vps_data and self.idx<len(vps_data[self.uid]): vps_data[self.uid].pop(self.idx); save_vps_data()
                    await interaction.response.edit_message(embed=success_embed("Deleted",f"`{self.cont}` removed."),view=None)
                except Exception as e: await interaction.response.edit_message(embed=error_embed("Failed",str(e)),view=None)
            @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, interaction:discord.Interaction, button:discord.ui.Button): await interaction.response.edit_message(embed=info_embed("Cancelled",""),view=None)
        await interaction.response.edit_message(embed=warn_embed("⚠️  Confirm Deletion",f"**Container:** `{vps['container_name']}`\nThis cannot be undone."),view=ConfirmDeleteView(self.user_id,self.vps_index,vps['container_name']))

@bot.command(name='manage')
async def manage_vps(ctx):
    uid=str(ctx.author.id); vlist=vps_data.get(uid,[])
    if not vlist: await ctx.send(embed=error_embed("No VPS","Use `{PREFIX}myvps` first.")); return
    if len(vlist)==1:
        vps=vlist[0]; status=await get_container_status(vps['container_name']); vps['status']=status; save_vps_data()
        view=VPSManageView(ctx,uid,0); await ctx.send(embed=view.build_manage_embed(vps,status),view=view)
    else:
        class VPSSelectView(discord.ui.View):
            def __init__(self): super().__init__(timeout=120); self.select=discord.ui.Select(placeholder="🖥️  Select VPS…",options=[discord.SelectOption(label=f"VPS #{i+1} — {v['container_name']}",value=str(i)) for i,v in enumerate(vlist)]); self.select.callback=self.on_select; self.add_item(self.select)
            async def on_select(self, interaction:discord.Interaction):
                if str(interaction.user.id)!=uid: await interaction.response.send_message(embed=error_embed("Denied","Not your VPS."),ephemeral=True); return
                idx=int(self.select.values[0]); vps=vlist[idx]; status=await get_container_status(vps['container_name']); vps['status']=status; save_vps_data()
                view=VPSManageView(ctx,uid,idx); await interaction.response.edit_message(embed=view.build_manage_embed(vps,status),view=view)
        await ctx.send(embed=info_embed("🎮  Select VPS",f"You have **{len(vlist)}** VPS instances. Choose one."),view=VPSSelectView())

@bot.command(name='start')
@is_admin()
async def admin_start_vps(ctx, container:str):
    try:
        await execute_lxc(f"lxc start {container}")
        for uid,vlist in vps_data.items():
            for vps in vlist:
                if vps['container_name']==container: vps['status']='running'; save_vps_data(); break
        await ctx.send(embed=success_embed("Started",f"`{container}` 🟢 Running"))
    except Exception as e: await ctx.send(embed=error_embed("Failed",str(e)))

@bot.command(name='stop')
@is_admin()
async def admin_stop_vps(ctx, container:str):
    try:
        await execute_lxc(f"lxc stop {container}")
        for uid,vlist in vps_data.items():
            for vps in vlist:
                if vps['container_name']==container: vps['status']='stopped'; save_vps_data(); break
        await ctx.send(embed=success_embed("Stopped",f"`{container}` 🔴 Stopped"))
    except Exception as e: await ctx.send(embed=error_embed("Failed",str(e)))

@bot.command(name='restart')
@is_admin()
async def admin_restart_vps(ctx, container:str):
    try:
        await execute_lxc(f"lxc restart {container}")
        for uid,vlist in vps_data.items():
            for vps in vlist:
                if vps['container_name']==container: vps['status']='running'; save_vps_data(); break
        await ctx.send(embed=success_embed("Restarted",f"`{container}` 🟢 Running"))
    except Exception as e: await ctx.send(embed=error_embed("Failed",str(e)))

@bot.command(name='delete')
@is_admin()
async def admin_delete_vps(ctx, container:str):
    try:
        try: await execute_lxc(f"lxc stop {container} --force")
        except: pass
        await execute_lxc(f"lxc delete {container} --force")
        for uid,vlist in vps_data.items():
            for i,vps in enumerate(vlist):
                if vps['container_name']==container: vlist.pop(i); break
        save_vps_data(); await ctx.send(embed=success_embed("Deleted",f"`{container}` removed."))
    except Exception as e: await ctx.send(embed=error_embed("Failed",str(e)))

@bot.command(name='suspend')
@is_admin()
async def suspend_vps(ctx, container:str, *, reason:str="No reason specified"):
    for uid,vlist in vps_data.items():
        for vps in vlist:
            if vps['container_name']==container:
                if vps.get('suspended'): await ctx.send(embed=warn_embed("Already Suspended","")); return
                try: await execute_lxc(f"lxc stop {container}")
                except: pass
                vps['suspended']=True; vps['status']='stopped'; vps['suspension_history'].append({"reason":reason,"date":datetime.now().isoformat()}); save_vps_data()
                await ctx.send(embed=build_embed("🔒  Suspended","",Colors.SUSPENDED)); return
    await ctx.send(embed=error_embed("Not Found",f"`{container}`"))

@bot.command(name='unsuspend')
@is_admin()
async def unsuspend_vps(ctx, container:str):
    for uid,vlist in vps_data.items():
        for vps in vlist:
            if vps['container_name']==container:
                if not vps.get('suspended'): await ctx.send(embed=warn_embed("Not Suspended","")); return
                vps['suspended']=False
                try: await execute_lxc(f"lxc start {container}"); vps['status']='running'
                except: vps['status']='stopped'
                save_vps_data(); await ctx.send(embed=success_embed("Unsuspended",f"`{container}`")); return
    await ctx.send(embed=error_embed("Not Found",f"`{container}`"))

@bot.command(name='whitelist')
@is_admin()
async def whitelist_vps(ctx, container:str):
    for uid,vlist in vps_data.items():
        for vps in vlist:
            if vps['container_name']==container: vps['whitelisted']=not vps.get('whitelisted',False); save_vps_data(); await ctx.send(embed=success_embed("Whitelist Updated","")); return
    await ctx.send(embed=error_embed("Not Found",f"`{container}`"))

@bot.command(name='add-admin')
@is_main_admin()
async def add_admin(ctx, user:discord.Member):
    uid=str(user.id)
    if uid in admin_data['admins']: await ctx.send(embed=warn_embed("Already Admin","")); return
    admin_data['admins'].append(uid); save_admin_data(); await ctx.send(embed=success_embed("Admin Added",f"{user.mention}"))

@bot.command(name='remove-admin')
@is_main_admin()
async def remove_admin(ctx, user:discord.Member):
    uid=str(user.id)
    if uid not in admin_data['admins']: await ctx.send(embed=warn_embed("Not Admin","")); return
    admin_data['admins'].remove(uid); save_admin_data(); await ctx.send(embed=success_embed("Admin Removed",f"{user.mention}"))

@bot.command(name='admins')
@is_admin()
async def list_admins(ctx):
    admin_list=[f"👑 <@{MAIN_ADMIN_ID}> — **Main Admin**"] + [f"🔧 <@{aid}>" for aid in admin_data['admins'] if aid!=str(MAIN_ADMIN_ID)]
    await ctx.send(embed=info_embed("🛡️  Admin Team","\n".join(admin_list)))

@bot.command(name='exec')
@is_admin()
async def exec_in_vps(ctx, container:str, *, command:str):
    try:
        result=await execute_lxc(f"lxc exec {container} -- bash -c \"{command}\"")
        if isinstance(result,bool): result="No output."
        await ctx.send(embed=success_embed("Executed",f"**Container:** `{container}`\n**Command:** `{command}`\n```\n{truncate(str(result),1900)}\n```"))
    except Exception as e: await ctx.send(embed=error_embed("Failed",str(e)))

@bot.command(name='vps-stats')
@is_admin()
async def vps_stats(ctx, container:str):
    try:
        status=await get_container_status(container); embed=info_embed(f"📊  Stats — {container}","")
        if status=='running':
            cpu_pct=await get_container_cpu_pct(container); ram_pct=await get_container_ram_pct(container); mem_str=await get_container_memory(container); disk_str=await get_container_disk(container)
            field(embed,"🖥️  CPU",f"{progress_bar(cpu_pct)}",True); field(embed,"🧠  RAM",f"{progress_bar(ram_pct)}\n› {mem_str}",True); field(embed,"🗄️  Disk",f"› {disk_str}",True)
        else: field(embed,"📊  Status",f"🔴 {status.title()}",True)
        await ctx.send(embed=embed)
    except Exception as e: await ctx.send(embed=error_embed("Error",str(e)))

@bot.command(name='all-vps')
@is_admin()
async def all_vps(ctx):
    if not vps_data: await ctx.send(embed=warn_embed("No VPS","")); return
    total=sum(len(v) for v in vps_data.values()); run=sum(1 for vl in vps_data.values() for v in vl if v.get('status')=='running' and not v.get('suspended'))
    embed=info_embed("📋  All VPS",f"**Total:** {total}  ·  🟢 Running: {run}\n{DIV}")
    count=0
    for uid,vlist in vps_data.items():
        for vps in vlist:
            if count>=20: break
            embed.add_field(name=f"🖥️  {vps['container_name']}",value=f"{status_badge(vps)}\n› <@{uid}>",inline=True); count+=1
    await ctx.send(embed=embed)

@bot.command(name='reinstall')
@is_admin()
async def admin_reinstall(ctx, container:str):
    for uid,vlist in vps_data.items():
        for i,vps in enumerate(vlist):
            if vps['container_name']==container:
                ram_val=int(vps['ram'].replace('GB','')); cpu_val=int(vps['cpu']); storage_val=int(vps['storage'].replace('GB',''))
                view=ReinstallOSSelectView(None,container,uid,i,ram_val,cpu_val,storage_val)
                await ctx.send(embed=warn_embed("🔄  Reinstall VPS",f"**Container:** `{container}`\n⚠️ All data will be wiped. Select OS below."),view=view); return
    await ctx.send(embed=error_embed("Not Found",f"`{container}`"))

@bot.command(name='status', aliases=['info', 'server', 'about'])
async def status_cmd(ctx):
    total_vps=sum(len(v) for v in vps_data.values()); running=sum(1 for vl in vps_data.values() for v in vl if v.get('status')=='running' and not v.get('suspended')); stopped=sum(1 for vl in vps_data.values() for v in vl if v.get('status')=='stopped' and not v.get('suspended')); suspended=sum(1 for vl in vps_data.values() for v in vl if v.get('suspended')); total_users=len(vps_data)
    host_cpu=get_cpu_usage(); host_ram=get_ram_usage(); lat=round(bot.latency*1000); health_pct=(running/total_vps*100) if total_vps>0 else 100.0
    total_ram_gb=0; total_cpu_ct=0; total_disk_gb=0
    for uid,vlist in vps_data.items():
        for vps in vlist:
            try: total_ram_gb+=int(vps['ram'].replace('GB',''))
            except: pass
            try: total_cpu_ct+=int(vps['cpu'])
            except: pass
            try: total_disk_gb+=int(vps['storage'].replace('GB',''))
            except: pass
    os_counts={}
    for uid,vlist in vps_data.items():
        for vps in vlist: os_name=vps.get('os_version','ubuntu:22.04'); os_counts[os_name]=os_counts.get(os_name,0)+1
    os_breakdown=""
    for os_name,count in sorted(os_counts.items(),key=lambda x:-x[1]):
        os_label=os_name
        for opt in OS_OPTIONS:
            if opt['value']==os_name: os_label=f"{opt.get('emoji','🐧')} {opt['label']}"; break
        os_breakdown+=f"› {os_label} — **{count}** instance(s)\n"
    if not os_breakdown: os_breakdown="› No VPS deployed yet."
    embed=build_embed("☁️  Welcome to CryzonCloud","*Powerful VPS Hosting, Built for Performance*\n{DIV}\n🚀 **CryzonCloud** is your premium LXC-based VPS platform.",Colors.PRIMARY)
    embed.set_image(url=BOT_ICON)
    field(embed,"🖥️  VPS Fleet Overview",f"```\n  Total Instances :  {total_vps}\n  🟢 Running      :  {running}\n  🔴 Stopped      :  {stopped}\n  🔒 Suspended    :  {suspended}\n  👥 Total Users   :  {total_users}\n```",False)
    health_emoji="🟢" if health_pct>=80 else "🟡" if health_pct>=50 else "🟠" if health_pct>=25 else "🔴"
    field(embed,f"{health_emoji}  Fleet Health",f"{progress_bar(health_pct)}\n› **{running}** of **{total_vps}** online" if total_vps>0 else "› No VPS deployed",False)
    field(embed,"💾  Resources Allocated",f"```\n  🧠 RAM   :  {total_ram_gb} GB\n  ⚙️ CPU   :  {total_cpu_ct} vCPU(s)\n  🗄️ Disk  :  {total_disk_gb} GB\n```",True)
    field(embed,"🖥️  Host System",f"› **CPU:** {progress_bar(host_cpu)}\n› **RAM:** {progress_bar(host_ram)}\n› **Latency:** `{lat} ms`",True)
    field(embed,"🐧  OS Distribution",os_breakdown,False)
    field(embed,"⚡  Platform Info",f"```\n  Name     :  CryzonCloud VPS Manager\n  Author   :  iTzTasin69\n  Engine   :  LXC Containers\n  Prefix   :  {PREFIX}\n```",True)
    field(embed,"🎮  Quick Commands",f"```\n{PREFIX}myvps       — Your VPS fleet\n{PREFIX}manage      — Control panel\n{PREFIX}status      — This page\n{PREFIX}help        — All commands\n```",True)
    await ctx.send(embed=embed)

# ══════════════════════════════════════════════
#  DYNAMIC ACTIVITY UPDATER
# ══════════════════════════════════════════════
async def activity_updater():
    await bot.wait_until_ready()
    cycle = 0
    statuses = [
        lambda r, t: f"⚡ CryzonCloud | {r}/{t} VPS Online",
        lambda r, t: f"☁️ Managing {t} VPS Instances",
        lambda r, t: f"🚀 {BOT_NAME}",
        lambda r, t: f"🖥️ {r} Servers Running",
        lambda r, t: f"⚡ by iTzTasin69 | {t} VPS",
    ]
    while not bot.is_closed():
        try:
            total_vps = sum(len(v) for v in vps_data.values())
            running = sum(1 for vl in vps_data.values() for v in vl if v.get('status') == 'running' and not v.get('suspended'))
            await bot.change_presence(
                status=discord.Status.online,
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name=statuses[cycle % len(statuses)](running, total_vps)
                )
            )
            cycle += 1
            await asyncio.sleep(60)
        except:
            await asyncio.sleep(60)

async def _setup_hook():
    asyncio.create_task(activity_updater())

bot.setup_hook = _setup_hook

@bot.command(name='help')
async def help_cmd(ctx):
    uid=str(ctx.author.id); is_adm=uid==str(MAIN_ADMIN_ID) or uid in admin_data.get("admins",[])
    embed=build_embed("📖  CryzonCloud Command Center",f"{DIV}",Colors.PURPLE)
    field(embed,"🎮  User Commands",f"```\n{PREFIX}ping        — Check latency\n{PREFIX}uptime      — Host uptime\n{PREFIX}myvps       — Your VPS fleet\n{PREFIX}manage      — VPS control panel\n{PREFIX}status      — Platform status\n{PREFIX}help        — This menu\n```",False)
    if is_adm:
        field(embed,"🛡️  Admin Commands",f"```\n{PREFIX}create <ram> <cpu> <disk> @user\n{PREFIX}start/stop/restart/delete <container>\n{PREFIX}suspend/unsuspend <container>\n{PREFIX}whitelist <container>\n{PREFIX}reinstall <container>\n{PREFIX}exec <container> <command>\n{PREFIX}vps-stats <container>\n{PREFIX}all-vps / lxc-list\n```",False)
    field(embed,"📡  Platform",f"**{BOT_NAME}** by **iTzTasin69**\n⚡ Powered by LXC  ·  🔒 Secure  ·  🚀 Fast",False)
    await ctx.send(embed=embed)

bot.run(DISCORD_TOKEN)
