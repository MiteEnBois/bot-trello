from datetime import datetime


class board:
    """
    Représente une board trello utilisée pour tenir compte des parties en cours

    ...

    Attributs
    ---------
    parties: dict
        dictionnaire représentant les parties. Format:
            id-carte-trello:{
                description: description de la partie. Pas exploité,
                joueurs: [liste d'id discords],
                label: status de la partie,
                mj: id discord du mj,
                systeme: système de la partie. Pas exploité,
                titre: titre de la partie
                }

    parties: dict
        dictionnaire représentant les parties ayant une date de prévue. Format:
            id-carte-trello:{
                date: date de la partie sous format datetime,
                description: description de la partie. Pas exploité,
                joueurs: [liste d'id discords],
                label: status de la partie,
                mj: id discord du mj,
                systeme: système de la partie. Pas exploité,
                titre: titre de la partie
                }

    users: dict
        dictionnaire liant les utilisateurs discord à une id trello. Si un utilisateur trello n'est pas lié à un compte discord, l'id utilisé sera l'id trello, suivi de '-trello'
        Format : 
            id_discord:{
                 mj: le nom de mj de cet utilisateur,
                trello: l'id trello,
                username: le pseudo
            }

    trello_id : dict
        dictionnaire liant les id trello aux id discord. L'inverse de users. Permet de trouver les id discord en partant des id trello sans avoir a tout parcourir. Sous exploité

    mjs : dict
        dictionnaire liant les noms de mj à une id. Sous exploité
    """

    def __init__(self, master):
        """
        Paramètre
        ---------
        master: dict
            un dictionnaire sorti de self.cree_dict()"""
        # self.parties = master["parties"].sort(key=lambda x: x["titre"])
        self.parties = {k: v for k, v in sorted(master["parties"].items(), key=lambda x: x[1]["titre"])}
        # self.prevues = master["prevues"].sort(key=lambda x: x["date"].replace(tzinfo=None) - datetime.utcnow())
        self.prevues = {k: v for k, v in sorted(master["prevues"].items(), key=lambda x: x[1]["date"].replace(tzinfo=None) - datetime.utcnow())}
        self.users = master["users"]
        self.trello_id = {}
        self.mjs = {}
        for u in self.users:
            if self.users[u]["mj"] is not None:
                self.mjs[self.users[u]["mj"]] = u
            self.trello_id[self.users[u]["trello"]] = u

    def cree_dict(self):
        """
        Crée un dictionnaire afin de le sauvegarder
        """
        return {"parties": self.parties, "users": self.users, "prevues": self.prevues}

    def get_partie(self, id):
        """
        Retourne un dictionnaire représentant une partie a partir d'une id. Retourne None si rien n'est trouvé
        """
        if id in self.parties:
            return self.parties[id]
        if id in self.prevues:
            return self.prevues[id]
        return None

    def usertostr(self, id):
        """Retourne une chaine de caractère représentant un user"""
        if id not in self.users:
            return None
        return f"{id} : **{self.users[id]['username']}**; nom de mj : {self.users[id]['mj']}; id trello : {self.users[id]['trello']}"
