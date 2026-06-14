# ══════════════════════════════════════════════
#  STATUS / INFO COMMAND — CryzonCloud Welcome
# ══════════════════════════════════════════════
@bot.command(name='status', aliases=['info', 'server', 'about'])
async def status_cmd(ctx):
    # ── Calculate Stats ──────────────────────
    total_vps   = sum(len(v) for v in vps_data.values())
    running     = sum(1 for vl in vps_data.values() for v in vl if v.get('status')=='running' and not v.get('suspended'))
    stopped     = sum(1 for vl in vps_data.values() for v in vl if v.get('status')=='stopped' and not v.get('suspended'))
    suspended   = sum(1 for vl in vps_data.values() for v in vl if v.get('suspended'))
    total_users = len(vps_data)
    admin_count = len(admin_data['admins']) + 1  # +1 for main admin

    host_cpu = get_cpu_usage()
    host_ram = get_ram_usage()
    host_up  = get_uptime()
    lat      = round(bot.latency * 1000)

    # ── VPS Health Percentage ────────────────
    health_pct = (running / total_vps * 100) if total_vps > 0 else 100.0

    # ── Total Resources Allocated ────────────
    total_ram_gb  = 0
    total_cpu_ct  = 0
    total_disk_gb = 0
    for uid, vlist in vps_data.items():
        for vps in vlist:
            try: total_ram_gb += int(vps['ram'].replace('GB',''))
            except: pass
            try: total_cpu_ct += int(vps['cpu'])
            except: pass
            try: total_disk_gb += int(vps['storage'].replace('GB',''))
            except: pass

    # ── OS Distribution ──────────────────────
    os_counts = {}
    for uid, vlist in vps_data.items():
        for vps in vlist:
            os_name = vps.get('os_version', 'ubuntu:22.04')
            os_counts[os_name] = os_counts.get(os_name, 0) + 1

    os_breakdown = ""
    for os_name, count in sorted(os_counts.items(), key=lambda x: -x[1]):
        os_label = os_name
        for opt in OS_OPTIONS:
            if opt['value'] == os_name:
                os_label = f"{opt.get('emoji','🐧')} {opt['label']}"
                break
        os_breakdown += f"› {os_label} — **{count}** instance(s)\n"
    if not os_breakdown:
        os_breakdown = "› No VPS deployed yet."

    # ── Build Embed ──────────────────────────
    embed = build_embed(
        "☁️  Welcome to CryzonCloud",
        f"*Powerful VPS Hosting, Built for Performance*\n{DIV}\n"
        f"🚀 **CryzonCloud** is your premium LXC-based VPS platform.\n"
        f"Manage, deploy, and monitor your virtual servers with ease.",
        Colors.PRIMARY
    )

    # ── Banner Image ─────────────────────────
    embed.set_image(url=BOT_ICON)

    # ── VPS Overview ─────────────────────────
    field(embed, "🖥️  VPS Fleet Overview",
        f"```\n"
        f"  Total Instances :  {total_vps}\n"
        f"  🟢 Running      :  {running}\n"
        f"  🔴 Stopped      :  {stopped}\n"
        f"  🔒 Suspended    :  {suspended}\n"
        f"  👥 Total Users   :  {total_users}\n"
        f"  🛡️ Admins        :  {admin_count}\n"
        f"```",
        False
    )

    # ── Fleet Health ─────────────────────────
    if health_pct >= 80:
        health_emoji = "🟢"
        health_text  = "Excellent"
    elif health_pct >= 50:
        health_emoji = "🟡"
        health_text  = "Good"
    elif health_pct >= 25:
        health_emoji = "🟠"
        health_text  = "Needs Attention"
    else:
        health_emoji = "🔴"
        health_text  = "Critical"

    field(embed, f"{health_emoji}  Fleet Health — {health_text}",
        f"{progress_bar(health_pct)}\n"
        f"› **{running}** of **{total_vps}** instances online" if total_vps > 0 else "› No VPS deployed yet",
        False
    )

    # ── Resources Allocated ──────────────────
    field(embed, "💾  Total Resources Allocated",
        f"```\n"
        f"  🧠 RAM   :  {total_ram_gb} GB\n"
        f"  ⚙️ CPU   :  {total_cpu_ct} vCPU(s)\n"
        f"  🗄️ Disk  :  {total_disk_gb} GB\n"
        f"```",
        True
    )

    # ── Host System ──────────────────────────
    field(embed, "🖥️  Host System",
        f"› **CPU:** {progress_bar(host_cpu)}\n"
        f"› **RAM:** {progress_bar(host_ram)}\n"
        f"› **Uptime:** `{host_up.split('up ')[1].split(',')[0] if 'up ' in host_up else 'N/A'}`\n"
        f"› **Latency:** `{lat} ms`",
        True
    )

    # ── OS Distribution ──────────────────────
    if len(os_breakdown) > 1024:
        os_breakdown = truncate(os_breakdown, 1024)
    field(embed, "🐧  OS Distribution", os_breakdown, False)

    # ── Platform Info ────────────────────────
    field(embed, "⚡  Platform Info",
        f"```\n"
        f"  Name     :  CryzonCloud VPS Manager\n"
        f"  Author   :  iTzTasin69\n"
        f"  Engine   :  LXC Containers\n"
        f"  Prefix   :  {PREFIX}\n"
        f"  Version  :  2.0 Ultra\n"
        f"```",
        True
    )

    # ── Quick Commands ───────────────────────
    field(embed, "🎮  Quick Commands",
        f"```\n"
        f"{PREFIX}myvps       — Your VPS fleet\n"
        f"{PREFIX}manage      — Control panel\n"
        f"{PREFIX}status      — This page\n"
        f"{PREFIX}help        — All commands\n"
        f"```",
        True
    )

    # ── Recent Activity ──────────────────────
    recent = []
    for uid, vlist in vps_data.items():
        for vps in vlist:
            created = vps.get('created_at', '')
            if created:
                recent.append((created, vps))
    recent.sort(key=lambda x: x[0], reverse=True)
    recent = recent[:5]

    if recent:
        activity_lines = ""
        for created, vps in recent:
            date_str = created[:16].replace('T', ' ')
            badge = "🟢" if vps.get('status')=='running' and not vps.get('suspended') else "🔴" if not vps.get('suspended') else "🔒"
            activity_lines += f"{badge} `{vps['container_name']}` — {date_str}\n"
        field(embed, "📋  Recent VPS", activity_lines, False)

    await ctx.send(embed=embed)

# ══════════════════════════════════════════════
#  DYNAMIC ACTIVITY UPDATER — Background Task
# ══════════════════════════════════════════════
async def activity_updater():
    """Updates bot presence every 60 seconds with live VPS count."""
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
            running   = sum(1 for vl in vps_data.values() for v in vl if v.get('status')=='running' and not v.get('suspended'))
            status_text = statuses[cycle % len(statuses)](running, total_vps)
            await bot.change_presence(
                status=discord.Status.online,
                activity=discord.Activity(type=discord.ActivityType.watching, name=status_text)
            )
            cycle += 1
            await asyncio.sleep(60)
        except Exception as e:
            logger.error(f"Activity updater error: {e}")
            await asyncio.sleep(60)

bot.loop.create_task(activity_updater())
