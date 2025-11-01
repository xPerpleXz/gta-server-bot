import discord
from discord.ext import commands, tasks
import aiohttp
import json
from datetime import datetime
import asyncio

# Bot Configuration
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Server Configuration - ÄNDERN SIE DIESE WERTE!
SERVER_IP = "DEINE_SERVER_IP"  # z.B. "123.456.789.0:30120"
CHANNEL_ID = 0  # Die Channel-ID wo der Status gepostet werden soll
UPDATE_INTERVAL = 60  # Sekunden zwischen Updates

# Global variables
status_message = None
server_data_cache = {
    'online': False,
    'players': 0,
    'max_players': 0,
    'server_name': 'Unknown'
}


async def query_ragemp_server(ip_port):
    """
    Fragt den RageMP Server ab und gibt Status zurück
    """
    try:
        # Teile IP und Port
        if ':' in ip_port:
            host, port = ip_port.rsplit(':', 1)
        else:
            host = ip_port
            port = '22005'
        
        # Versuche verschiedene RageMP API Endpoints
        
        # Methode 1: Versuche HTTP Info API
        try:
            url = f"http://{host}:{port}/api/info"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'online': True,
                            'server_name': data.get('name', 'GTA Grand DE 1'),
                            'players': data.get('players', 0),
                            'max_players': data.get('maxPlayers', 100)
                        }
        except Exception as e:
            print(f"HTTP Info API Fehler: {e}")
        
        # Methode 2: Versuche Master List API
        try:
            url = "https://cdn.rage.mp/master/"
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Suche nach unserem Server in der Liste
                        for server in data:
                            server_addr = f"{server.get('ip')}:{server.get('port')}"
                            if host in server.get('ip', '') or server_addr == ip_port:
                                return {
                                    'online': True,
                                    'server_name': server.get('name', 'GTA Grand DE 1'),
                                    'players': server.get('players', 0),
                                    'max_players': server.get('maxplayers', 100)
                                }
        except Exception as e:
            print(f"Master List API Fehler: {e}")
        
        # Methode 3: Einfacher Socket Test (prüft nur ob Server online ist)
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, int(port)))
            sock.close()
            
            if result == 0:
                return {
                    'online': True,
                    'server_name': 'GTA Grand DE 1',
                    'players': 0,
                    'max_players': 100
                }
        except Exception as e:
            print(f"Socket Test Fehler: {e}")
        
    except Exception as e:
        print(f"Fehler beim Abfragen des Servers: {e}")
    
    return {
        'online': False,
        'server_name': 'GTA Grand DE 1',
        'players': 0,
        'max_players': 0
    }


def create_status_embed(server_info):
    """
    Erstellt ein Discord Embed mit Server-Status
    """
    if server_info['online']:
        embed = discord.Embed(
            title=f"🟢 {server_info['server_name']}",
            description="**Server ist ONLINE**",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        
        # Spieler Fortschrittsbalken
        player_percentage = (server_info['players'] / server_info['max_players'] * 100) if server_info['max_players'] > 0 else 0
        bar_length = 20
        filled = int(bar_length * player_percentage / 100)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        embed.add_field(
            name="👥 Spieler",
            value=f"`{bar}` {server_info['players']}/{server_info['max_players']}",
            inline=False
        )
        
        # Server IP
        embed.add_field(
            name="🔗 Server Adresse",
            value=f"`{SERVER_IP}`",
            inline=False
        )
        
        # Auslastung als Prozent
        embed.add_field(
            name="📊 Auslastung",
            value=f"{player_percentage:.1f}%",
            inline=True
        )
        
    else:
        embed = discord.Embed(
            title=f"🔴 {server_info['server_name']}",
            description="**Server ist OFFLINE**",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="ℹ️ Status",
            value="Der Server konnte nicht erreicht werden.",
            inline=False
        )
    
    embed.set_footer(text="Letztes Update")
    return embed


@bot.event
async def on_ready():
    """
    Wird ausgeführt wenn der Bot online ist
    """
    print(f'{bot.user} ist jetzt online!')
    print(f'Bot ID: {bot.user.id}')
    print('------')
    
    # Starte den Status-Update Loop
    if not update_server_status.is_running():
        update_server_status.start()


@tasks.loop(seconds=UPDATE_INTERVAL)
async def update_server_status():
    """
    Aktualisiert den Server-Status regelmäßig
    """
    global status_message, server_data_cache
    
    # Frage Server-Status ab
    server_info = await query_ragemp_server(SERVER_IP)
    server_data_cache = server_info
    
    # Erstelle Embed
    embed = create_status_embed(server_info)
    
    # Hole den Channel
    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print(f"Channel mit ID {CHANNEL_ID} nicht gefunden!")
        return
    
    try:
        if status_message is None:
            # Sende neue Nachricht
            status_message = await channel.send(embed=embed)
        else:
            # Aktualisiere existierende Nachricht
            await status_message.edit(embed=embed)
    except discord.NotFound:
        # Nachricht wurde gelöscht, sende neue
        status_message = await channel.send(embed=embed)
    except Exception as e:
        print(f"Fehler beim Update: {e}")


@bot.command(name='status')
async def manual_status(ctx):
    """
    Zeigt den aktuellen Server-Status manuell an
    """
    server_info = await query_ragemp_server(SERVER_IP)
    embed = create_status_embed(server_info)
    await ctx.send(embed=embed)


@bot.command(name='setserver')
@commands.has_permissions(administrator=True)
async def set_server(ctx, ip: str):
    """
    Ändert die Server-IP (nur für Admins)
    """
    global SERVER_IP
    SERVER_IP = ip
    await ctx.send(f"✅ Server-IP wurde auf `{ip}` gesetzt!")


@bot.command(name='setchannel')
@commands.has_permissions(administrator=True)
async def set_channel(ctx):
    """
    Setzt den aktuellen Channel als Status-Channel (nur für Admins)
    """
    global CHANNEL_ID, status_message
    CHANNEL_ID = ctx.channel.id
    status_message = None  # Reset die Status-Nachricht
    await ctx.send(f"✅ Status-Channel wurde auf diesen Channel gesetzt!")


@bot.command(name='serverinfo')
async def server_info(ctx):
    """
    Zeigt detaillierte Server-Informationen
    """
    embed = discord.Embed(
        title="📋 Bot Information",
        color=discord.Color.blue()
    )
    embed.add_field(name="Server IP", value=f"`{SERVER_IP}`", inline=False)
    embed.add_field(name="Update Intervall", value=f"{UPDATE_INTERVAL} Sekunden", inline=True)
    embed.add_field(name="Status Channel", value=f"<#{CHANNEL_ID}>", inline=True)
    embed.add_field(
        name="Aktueller Status",
        value=f"{'🟢 Online' if server_data_cache['online'] else '🔴 Offline'}",
        inline=True
    )
    await ctx.send(embed=embed)


@bot.command(name='help_server')
async def help_command(ctx):
    """
    Zeigt alle verfügbaren Befehle
    """
    embed = discord.Embed(
        title="🤖 Server Bot Befehle",
        description="Hier sind alle verfügbaren Befehle:",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="!status",
        value="Zeigt den aktuellen Server-Status an",
        inline=False
    )
    embed.add_field(
        name="!serverinfo",
        value="Zeigt Bot-Konfiguration und Informationen",
        inline=False
    )
    embed.add_field(
        name="!setserver <IP:Port>",
        value="Ändert die Server-IP (Admin)",
        inline=False
    )
    embed.add_field(
        name="!setchannel",
        value="Setzt den aktuellen Channel als Status-Channel (Admin)",
        inline=False
    )
    
    await ctx.send(embed=embed)


# Bot starten
if __name__ == "__main__":
    import os
    
    # Versuche zuerst Environment Variables (für Railway/Heroku)
    TOKEN = os.getenv('DISCORD_TOKEN')
    if os.getenv('SERVER_IP'):
        SERVER_IP = os.getenv('SERVER_IP')
    if os.getenv('CHANNEL_ID'):
        CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
    if os.getenv('UPDATE_INTERVAL'):
        UPDATE_INTERVAL = int(os.getenv('UPDATE_INTERVAL'))
    
    # Falls keine Environment Variables, lade aus config.json
    if not TOKEN:
        try:
            with open('config.json', 'r') as f:
                config = json.load(f)
                TOKEN = config.get('token')
                SERVER_IP = config.get('server_ip', SERVER_IP)
                CHANNEL_ID = config.get('channel_id', CHANNEL_ID)
                UPDATE_INTERVAL = config.get('update_interval', UPDATE_INTERVAL)
        except FileNotFoundError:
            print("FEHLER: Weder Environment Variables noch config.json gefunden!")
            print("Bitte setze DISCORD_TOKEN als Environment Variable")
            print("oder erstelle eine config.json Datei.")
            exit(1)
    
    if not TOKEN:
        print("FEHLER: Kein Discord Token gefunden!")
        print("Setze DISCORD_TOKEN als Environment Variable")
        print("oder füge den Token in config.json ein.")
        exit(1)
    
    print("=" * 50)
    print("🤖 GTA Grand DE Server Status Bot")
    print("=" * 50)
    print(f"📡 Server: {SERVER_IP}")
    print(f"📢 Channel ID: {CHANNEL_ID if CHANNEL_ID else 'Noch nicht gesetzt'}")
    print(f"🔄 Update Intervall: {UPDATE_INTERVAL} Sekunden")
    print("=" * 50)
    print("🚀 Bot startet...")
    print()
        
    bot.run(TOKEN)
