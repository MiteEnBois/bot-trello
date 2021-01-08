from trello import TrelloClient
import math
import os
import asyncio
from discord.ext import commands
from discord import Intents
import discord
from datetime import datetime
from dotenv import load_dotenv
import yaml
from board import board
from difflib import get_close_matches

# pip freeze > requirements.txt
# virtualenv venv
# source venv/bin/activate
# pip install -r requirements.txt

# ----------------------------- SETUP VARIABLES GLOBALES ET BOT
print("start loading")

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

intents = Intents.default()
intents.members = True

bot = commands.Bot(command_prefix='t!', intents=intents)


client = TrelloClient(
    api_key=os.getenv('KEY'),
    api_secret=os.getenv('SECRET_KEY'),
    token=os.getenv('TRELLO_TOKEN')
)

all_boards = client.list_boards()
orga = all_boards[-1]
if orga.name != "Organisation des Parties de JDR":
    print("erreur")
labels = orga.get_labels()
dictLabels = {}
for l in labels:
    dictLabels[l.id] = l.name

board_master = None

with open("master.yml", encoding='utf-8') as f:
    data = yaml.load(f, Loader=yaml.FullLoader)
    if data is None:
        data = {"parties": {}, "users": {}, "prevues": {}}
    board_master = board(data)

    f.close()

# ----------------------------- FONCTIONS UTILITAIRES


async def confirmation(ctx, message, confirmation):
    conf = await ctx.send(
        f"{message}\nEnvoyez {confirmation} pour confirmer, sinon ne répondez pas"
    )

    def check(m):
        return m.content == confirmation and m.channel == ctx.channel and m.author == ctx.author

    try:
        resp = await bot.wait_for("message", check=check, timeout=30)
        await conf.delete()
        await resp.delete()
        return True

    except asyncio.TimeoutError:
        await conf.edit(content="Timeout")
        await asyncio.sleep(10)
        await conf.delete()
        return False


def maj_master():
    """Sauvegarde la base de donnée en mémoire vers un fichier"""
    with open("master.yml", mode="w+", encoding='utf-8') as f:
        f.truncate(0)
        yaml.dump(board_master.cree_dict(), f)
        f.close()


def maj_board():
    """Met a jour la board

    Compare d'abords les users présent dans la base de donnée et ceux présent sur la board trello, rajoute dans la base de donnée si ils n'y sont pas déjà présent, 
    et les enleves de la base de donnée si ils se sont retiré de la board

    Tente ensuite de rajouter toute les cartes de la board trello; si elle est déjà présente, passe cette étape
    Enlève les parties de la base de données si elles ne sont plus sur la board trello
    """
    changes = {"added": [], "removed": []}
    cards = []
    present_users = board_master.users.copy()
    all_members = orga.all_members().copy()

    for m in orga.all_members():
        for u in board_master.users:
            if str(board_master.users[u]['trello']) == str(m.id):
                present_users.pop(u, None)
                all_members.remove(m)

    # print("-----------------")
    # print("present users:\n")
    # for u in present_users:
    #     print(f"\t{u} : {present_users[u]['username']} - {present_users[u]['trello']}")
    # print("all_members:\n")
    # for m in all_members:
    #     print(f"\t{m.id} : {m.username}")

    if len(present_users) > 0:
        for u in present_users:
            changes["removed"].append(present_users[u]["username"])
            board_master.users.pop(u, None)
    if len(all_members) > 0:
        for m in all_members:
            board_master.users[m.id+"-trello"] = {'mj': None, "trello": m.id, "username": m.username}
            board_master.trello_id[m.id] = m.username
            changes["added"].append(m.username)
    for x in board_master.prevues:
        cards.append(x)
    for x in board_master.parties:
        cards.append(x)

    for card in orga.visible_cards():
        if card.id in cards:
            cards.remove(card.id)
            continue

        print(card.name)
        changes["added"].append(card.name)
        label = ""
        for l in card.idLabels:
            label += dictLabels[l]+", "
        if len(label) > 0 and label[-2] == ",":
            label = label[:-2]
        p = {"titre": card.name,
             "mj": "",
             "label": label,
             "systeme": "",
             "description": card.description
             }
        joueurs = []
        for id in card.idMembers:
            for u in board_master.users:
                if p["mj"] != "" and u in board_master.mjs:
                    p["mj"] = u
                if board_master.users[u]["trello"] == id:
                    joueurs.append(u)
            p["mj"] = id
        p["joueurs"] = joueurs
        if "(MJ)" in card.get_list().name:
            if p["mj"] == "":
                p["mj"] = card.get_list().replace("(MJ) ", "")
            board_master.parties[card.id] = p
        else:
            p["date"] = card.due_date
            board_master.prevues[card.id] = p
    if len(cards) != 0:
        print(cards)
        for c in cards:
            if c in board_master.parties:
                changes["removed"].append(board_master.parties[c]["titre"])
                board_master.parties.pop(c, None)
            if c in board_master.prevues:
                changes["removed"].append(board_master.prevues[c]["titre"])
                board_master.prevues.pop(c, None)

    maj_master()
    return changes


def partie_to_embed(id, partie, color):
    mj = "MJ : "
    if partie["mj"] not in board_master.users:
        if partie["mj"] == "":
            mj = "Pas de mj"
        else:
            mj += partie["mj"]
    else:
        mj += board_master.users[partie["mj"]]["username"]
    if "date" in partie:
        mj = ''
    embed = discord.Embed(title=partie["titre"], description=mj, color=color)
    footer = ""
    if partie["label"] != "":
        footer += f'{partie["label"]}; '
    footer += f"id : {id}"
    embed.set_footer(text=footer)
    if partie["description"] != '':
        embed.add_field(name="Description", value=partie["description"], inline=False)
    if partie["systeme"] != '':
        embed.add_field(name="Système", value=partie["systeme"], inline=False)
    joueurs = ""
    for j in partie["joueurs"]:
        if j != partie["mj"]:
            joueurs += f'{board_master.users[j]["username"]}, '
    embed.add_field(name="Joueurs", value=joueurs[:-2], inline=False)
    if "date" in partie:
        date = partie["date"]
        delta = date.replace(tzinfo=None) - datetime.utcnow()
        titre = f"{date.strftime('%d/%m/%Y')} "
        if delta.days < 0:
            titre += "(Date dépassée)"
        elif delta.days == 0:
            titre += "(Prévue pour aujourd'hui"
            if delta.seconds >= 3600:
                titre += f" dans {math.floor(delta.seconds/3600)}h)"
            else:
                titre += f" dans {math.floor(delta.seconds/60)}m)"
        elif delta.days == 1:
            titre += f"(Prévue pour demain)"
        else:
            titre += f"(Prévue pour dans {delta.days} jours)"
        embed.add_field(name="Date", value=titre, inline=False)
    return embed


def trouve_discord_id(ctx, id):
    """Détermine si une id entrée est 'valide'"""
    if id == "" or id == "0" or id == 0:
        return ctx.author.id
    else:
        try:
            discord_id = int(id)
        except ValueError:
            discord_id = ctx.message.mentions[0].id
    return discord_id


def trouve_partie(terme):
    """Cherche une partie à partir d'un nom

    Utilise difflib.get_close_matches pour obtenir une liste des parties qui ressemble le plus au nom donné.
    Ne marche pas bien pour trouver un nom long avec un terme court et vice versa"""
    parties = {}
    for key, value in board_master.parties.items():
        if value["titre"] in parties:
            parties[value["titre"]+" (duplicata)"] = key
        else:
            parties[value["titre"]] = key

    for key, value in board_master.prevues.items():
        if value["titre"] in parties:
            parties[value["titre"]+"+"] = key
        else:
            parties[value["titre"]] = key

    t = []
    num = 0.7
    while len(t) <= 0 or num == 0:
        num -= 0.05
        t = get_close_matches(terme, parties, n=3, cutoff=num)
    response = []
    for x in t:

        response.append(parties[x])
    return response


# ----------------------------- COMMANDES


@bot.command(name='ping', help='Pong!')
async def ping(ctx):
    await ctx.send("Pong!")


@bot.command(name='pong', help='Ping!')
async def pong(ctx):
    await ctx.send("Ping!")


help = """Affiche les parties dont vous êtes le maitre de jeu
        Rajoutez une mention ou un id pour spécifier une personne autre que vous"""


@bot.command(name='mj', help=help)
async def mj(ctx, id=""):
    discord_id = trouve_discord_id(ctx, id)
    if discord_id not in board_master.users:
        print("erreur : id pas trouvée")
        await ctx.send("Vous n'êtes pas présent sur trello, ou vous n'avez pas été lié à votre compte discord. Utilisez t!linktrello")
        return
    if board_master.users[discord_id]["mj"] is None:
        print("erreur : pas mj")
        await ctx.send("Vous ne meujeutez pas de partie!")
        return

    for id, p in board_master.parties.items():
        if p["mj"] == discord_id:
            await ctx.send(embed=partie_to_embed(id, p, 0x0151e4))


help = """Affiche les parties prévues auquelles vous participez
        Rajoutez une mention ou un id pour spécifier une personne autre que vous"""


@bot.command(name='prevu', help=help)
async def prevu(ctx, id=''):
    discord_id = trouve_discord_id(ctx, id)
    if discord_id not in board_master.users:
        print("erreur : id pas trouvée")
        await ctx.send("Vous n'êtes pas présent sur trello, ou vous n'avez pas été lié à votre compte discord. Utilisez t!linktrello")
        return
    for id, p in board_master.prevues.items():
        if discord_id in p["joueurs"]:
            await ctx.send(embed=partie_to_embed(id, p, 0x00750e))

help = """Affiche toutes les parties prévues auquelles vous participez
        Rajoutez une mention ou un id pour spécifier une personne autre que vous"""


@bot.command(name='liste', help=help)
async def liste(ctx, id=''):
    discord_id = trouve_discord_id(ctx, id)
    if discord_id not in board_master.users:
        print("erreur : id pas trouvée")
        await ctx.send("Vous n'êtes pas présent sur trello, ou vous n'avez pas été lié à votre compte discord. Utilisez t!linktrello")
        return
    for id, p in board_master.parties.items():
        if discord_id in p["joueurs"]:
            await ctx.send(embed=partie_to_embed(id, p, 0xf48f01))

help = """Affiche un combo des commandes liste et prevu
        Rajoutez une mention ou un id pour spécifier une personne autre que vous"""


@bot.command(name='resume', help=help)
async def resume(ctx, id=''):
    discord_id = trouve_discord_id(ctx, id)
    for id, p in board_master.parties.items():
        if discord_id in p["joueurs"]:
            await ctx.send(embed=partie_to_embed(id, p, 0xf48f01))
    for id, p in board_master.prevues.items():
        if discord_id in p["joueurs"]:
            await ctx.send(embed=partie_to_embed(id, p, 0x00750e))

help = """Permet de changer le pseudo qu'utilise le bot pour parler de vous"""


@bot.command(name='pseudo', help=help)
async def pseudo(ctx, *arr):
    new = ' '.join(arr)
    discord_id = ctx.author.id
    if discord_id not in board_master.users:
        print("erreur : id pas trouvée")
        await ctx.send("Vous n'êtes pas présent sur trello, ou vous n'avez pas été lié à votre compte discord. Utilisez t!linktrello")
        return
    old = board_master.users[discord_id]["username"]
    board_master.users[discord_id]["username"] = new
    if not await confirmation(ctx, f"Vous vous appretez à changer votre username de {old} à {new}, souhaitez-vous continuer?", "Oui"):
        return
    board_master.trello_id[board_master.users[discord_id]["trello"]] = new
    maj_master()
    await ctx.send(f"Username changé de {old} à {new}")


help = """Trouve une partie a partir d'un nom
        Ne marche pas bien avec un titre de partie long et un nom donné court"""


@bot.command(name='cherchepartie', help=help)
async def cherchepartie(ctx, *arr):
    titre = ' '.join(arr)
    found = trouve_partie(titre)
    if len(found) > 0:
        for partie in found:
            if partie in board_master.parties:
                await ctx.send(embed=partie_to_embed(partie, board_master.parties[partie], 0xf48f01))
            elif partie in board_master.prevues:
                await ctx.send(embed=partie_to_embed(partie, board_master.prevues[partie], 0x00750e))
            else:
                await ctx.send(f"erreur : {partie} pas trouvée")
    else:
        await ctx.send(f"Pas trouvé :(")


help = """Ping tout les joueurs d'une partie"""


@bot.command(name='pingjoueurs', help=help)
async def pingjoueurs(ctx, id):
    partie = board_master.get_partie(id)
    if partie is None:
        await ctx.send(f"ID incorrect")
        return
    if not await confirmation(ctx, f"Vous vous appretez à pinger plusieurs personnes, souhaitez-vous continuer?", "Oui"):
        return
    msg = f"{ctx.author.mention} vous ping tous concernant **{partie['titre']}**: "
    for j in partie["joueurs"]:
        if j == ctx.author.id:
            continue
        user = ctx.guild.get_member(int(j))
        if user is None:
            msg += board_master.users[j]["username"]+', '
            continue
        msg += user.mention+', '
    await ctx.send(msg[:-2])


help = """Met à jour les données"""


@bot.command(name='maj', help=help)
async def maj(ctx):
    changes = maj_board()
    txt = "**Update effectuée :**\n"
    if changes["added"] != []:
        txt += "Rajouté:\n   "
        for a in changes["added"]:
            txt += a+", "
        txt = txt[:-2]+"\n   "
    if changes["removed"] != []:
        txt += "Enlevés:\n"
        for a in changes["removed"]:
            txt += a+", "
        txt = txt[:-2]
    if txt == "**Update effectuée :**\n":
        txt += "Pas de changements"
    await ctx.send(txt)

help = """Link une id trello à une id discord

        Lancez seul si vous voulez la liste des ids à linker
        Lancez avec une id trello finissant par '-trello' (trouvé au préalable avec t!linktrello) pour vous linker avec l'id
        Lancez avec une id trello finissant par '-trello' (trouvé au préalable avec t!linktrello) et une id discord pour lier les 2"""


@bot.command(name='linktrello', help=help)
async def linktrello(ctx, trello_id="", discord_id=0):
    if trello_id == "":
        txt = ""
        for t in board_master.users:
            if "-trello" in str(t):
                txt += board_master.usertostr(t)+"\n"
        if txt == "":
            txt = "Pas d'id trello à linker"
        else:
            txt = "ID Trello devant etre linké. Si vous désirez vous linker, utilisez la commande t!linktrello [id]\n"+txt
        await ctx.send(txt)
    else:
        if discord_id == 0:
            discord_id = ctx.author.id
        else:
            discord_id = trouve_discord_id(ctx, discord_id)
        if discord_id in board_master.users:
            if board_master.users[discord_id]["trello"] == trello_id:
                await ctx.send(f"Les ID sont déjà liés : {board_master.usertostr(discord_id)}")
                return
            if not await confirmation(ctx, f"L'id discord est déjà lié à une autre id trello ({board_master.usertostr(discord_id)}), souhaitez vous la changer?", "Oui"):
                return
            board_master.users[discord_id]["trello"] = trello_id
            await ctx.send("Lien changé ({board_master.usertostr(discord_id)})")
            return
        if trello_id not in board_master.users:
            await ctx.send("ID trello non présente")
            return
        if not await confirmation(ctx, f"Vous allez link l'id trello ({board_master.usertostr(trello_id)}) avec l'id discord {discord_id}, souhaitez vous continuer?", "Oui"):
            return
        board_master.users[discord_id] = board_master.users[trello_id].copy()
        board_master.users.pop(trello_id, None)
        await ctx.send(f"Lien confirmé ({board_master.usertostr(discord_id)})")
        maj_master()
# ----------------------------- FIN SETUP

# S'execute quand le bot est prêt; Affiche la liste des serveurs sur lesquelles le bot est actuellement


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    await bot.process_commands(message)


@bot.event
async def on_ready():
    print(maj_board())
    await bot.change_presence(activity=discord.Game(f"{bot.command_prefix}help"))
    print(f'{bot.user} is connected to the following guild:')
    for guild in bot.guilds:
        print(f'-{guild.name}')
    print(f'{bot.user} has started')


# lance le bot
bot.run(TOKEN)
