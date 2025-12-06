#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pygame
import sys
import random
import time
from queue import Queue
from threading import Thread


from ivy.ivy import IvyServer
IVY_AVAILABLE = True


# --- Constantes ---
WIDTH, HEIGHT = 800, 600
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
RED = (255, 0, 0)

COLORS = {
    'RED': (255, 0, 0),
    'ORANGE': (255, 165, 0),
    'YELLOW': (255, 255, 0),
    'GREEN': (0, 255, 0),
    'BLUE': (0, 0, 255),
    'PURPLE': (128, 0, 128),
    'BLACK': (50, 50, 50),
    'SELECT': None,   # prendre la couleur sous la souris
    'none': (50, 50, 50)  # Couleur par défaut : BLACK
}

DEFAULT_COLOR = (50, 50, 50)  # BLACK

# Timeout pour la fusion (en secondes)
FUSION_TIMEOUT = 3.0

# --- États FSM du contrôleur de dialogue ---
class DialogState:
    IDLE = "IDLE"
    WAITING_SHAPE = "WAITING_SHAPE"
    WAITING_COLOR = "WAITING_COLOR"
    WAITING_LOCATION = "WAITING_LOCATION"
    WAITING_TARGET = "WAITING_TARGET"
    WAITING_MOVE_DEST = "WAITING_MOVE_DEST"
    COMPLETE = "COMPLETE"

# --- Structure de données pour la fusion ---
class FusionData:
    """Structure contenant les informations accumulées pour la fusion multimodale"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Réinitialise toutes les données de fusion"""
        self.action = None
        self.shape = None
        self.color = None
        self.location = None
        self.target_shape = None
        self.deictic_location = False  # "ici", "là"
        self.deictic_color = False     # "de cette couleur"
        self.deictic_target = False    # "cette forme", "ça"
        self.click_position = None
        self.mouse_position = None     # Position de la souris (sans clic)
        self.gesture = None
        self.timestamp = None
        
    def is_complete_create(self):
        if self.action != "CREATE" or not self.shape:
            return False
        
        if self.deictic_location and not self.click_position:
            return False
            
        return True
    
    def is_complete_move(self):
        if self.action != "MOVE":
            return False
        
        # MOVE THIS THERE : on a besoin du pointage (THIS) et de la destination (THERE)
        if self.deictic_target:
            # On doit avoir la position de la souris pour trouver l'objet
            if not self.mouse_position:
                return False
            # Et on doit avoir la destination
            if self.deictic_location and not self.click_position:
                return False
            return self.deictic_location  # On attend la destination
        
        # MOVE CIRCLE THERE : on a la forme, on attend la destination
        if self.shape:
            if self.deictic_location and not self.click_position:
                return False
            return self.deictic_location
        
        return False
    
    def is_complete_delete(self):
        if self.action != "DELETE":
            return False
        
        # DELETE sans localisation = tout effacer
        if not self.deictic_location:
            return True
            
        # DELETE avec localisation = effacer l'objet cliqué
        if self.deictic_location and self.click_position:
            return True
            
        return False
    
    def is_complete_quit(self):
        """Vérifie si on a la commande QUIT"""
        return self.action == "QUIT"
    
    def is_expired(self):
        """Vérifie si le timeout est dépassé"""
        if not self.timestamp:
            return False
        return (time.time() - self.timestamp) > FUSION_TIMEOUT
    
    def add_speech_info(self, parsed_data):
        """Ajoute les informations de la reconnaissance vocale"""
        if not self.timestamp:
            self.timestamp = time.time()
            
        if 'action' in parsed_data and parsed_data['action']:
            self.action = parsed_data['action']
            
        if 'form' in parsed_data and parsed_data['form']:
            self.shape = parsed_data['form']
            
        if 'color' in parsed_data and parsed_data['color']:
            self.color = parsed_data['color']
            
        if 'localisation' in parsed_data and parsed_data['localisation'] == 'THERE':
            self.deictic_location = True
            
        if 'pointage' in parsed_data and parsed_data['pointage'] == 'THIS':
            self.deictic_target = True
    
    def add_gesture_info(self, gesture_name):
        """Ajoute l'information gestuelle"""
        if not self.timestamp:
            self.timestamp = time.time()
        self.gesture = gesture_name
        
        # Mapping geste -> forme ou action
        if gesture_name in ['circle', 'cercle']:
            self.shape = 'CIRCLE'
        elif gesture_name in ['rectangle', 'carre']:
            self.shape = 'RECTANGLE'
        elif gesture_name in ['triangle']:
            self.shape = 'TRIANGLE'
        elif gesture_name in ['diamond', 'losange']:
            self.shape = 'DIAMOND'
        elif gesture_name in ['create', 'creer']:
            self.action = 'CREATE'
        elif gesture_name in ['move', 'deplacer']:
            self.action = 'MOVE'
    
    def add_click_info(self, position):
        """Ajoute l'information de clic"""
        if not self.timestamp:
            self.timestamp = time.time()
        self.click_position = position
    
    def add_mouse_position(self, position):
        """Ajoute la position de la souris (sans clic)"""
        self.mouse_position = position
    
    def __str__(self):
        return f"FusionData(action={self.action}, shape={self.shape}, " \
               f"color={self.color}, loc={self.deictic_location}, " \
               f"click={self.click_position})"

# --- Classes Formes ---
class Forme:
    def __init__(self, pos, color=None, shape_type=""):
        self.x, self.y = pos
        self.color = color if color else DEFAULT_COLOR
        self.shape_type = shape_type

    def set_location(self, pos):
        self.x, self.y = pos

    def set_color(self, color):
        self.color = color

    def distance_to(self, pos):
        return ((self.x - pos[0])**2 + (self.y - pos[1])**2)**0.5

    def is_clicked(self, pos, threshold=40):
        return self.distance_to(pos) < threshold

    def draw(self, screen):
        pass
    
    def get_type(self):
        return self.shape_type

class Cercle(Forme):
    def __init__(self, pos, color=None):
        super().__init__(pos, color if color else DEFAULT_COLOR, "CIRCLE")
        
    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), 30)

class Rectangle(Forme):
    def __init__(self, pos, color=None):
        super().__init__(pos, color if color else DEFAULT_COLOR, "RECTANGLE")
        
    def draw(self, screen):
        pygame.draw.rect(screen, self.color, (int(self.x)-30, int(self.y)-20, 60, 40))

class Triangle(Forme):
    def __init__(self, pos, color=None):
        super().__init__(pos, color if color else DEFAULT_COLOR, "TRIANGLE")
        
    def draw(self, screen):
        points = [(int(self.x), int(self.y)-30), 
                  (int(self.x)+30, int(self.y)+30), 
                  (int(self.x)-30, int(self.y)+30)]
        pygame.draw.polygon(screen, self.color, points)

class Losange(Forme):
    def __init__(self, pos, color=None):
        super().__init__(pos, color if color else DEFAULT_COLOR, "DIAMOND")
        
    def draw(self, screen):
        points = [(int(self.x), int(self.y)-30), 
                  (int(self.x)+30, int(self.y)), 
                  (int(self.x), int(self.y)+30), 
                  (int(self.x)-30, int(self.y))]
        pygame.draw.polygon(screen, self.color, points)

# --- Ivy Listener ---
if IVY_AVAILABLE:
    class IvyListener(IvyServer):
        def __init__(self, queue):
            super().__init__(agent_name="FusionEngine")
            self.queue = queue
            
            # Messages SRA5 (reconnaissance vocale) - format exact du bus
            # Format: sra5 Parsed=action=CREATE where=THIS form=CIRCLE color=RED localisation=THERE
            self.bind_msg(self.on_sra5_message, r'^sra5 Parsed=action=(\w+) where=([^ ]*) form=(\w+) color=(\w+)(?: localisation=([^ ]*))?.*')
            
            # Messages du recognizer de gestes
            self.bind_msg(self.on_gesture_message, r'^Recognizer gesture=(.*) score=(.*)')
            
        def on_sra5_message(self, src, action, where, form, color, localisation=None):
            """Traite les messages de reconnaissance vocale SRA5"""
            msg = {
                "action": action if action != "none" else None,
                "pointage": where if where not in ("none", "undefined", "") else None,
                "form": form if form != "none" else None,
                "color": color if color != "none" else None,
                "localisation": localisation if localisation not in (None, "", "none", "undefined") else None,
            }
            print(f"[Ivy SRA5] Received: {msg}")
            
            # Convertir en format texte pour process_speech
            parts = []
            if msg["action"]:
                parts.append(f"action={msg['action']}")
            if msg["pointage"]:
                parts.append(f"pointage={msg['pointage']}")
            if msg["form"]:
                parts.append(f"form={msg['form']}")
            if msg["color"]:
                parts.append(f"color={msg['color']}")
            if msg["localisation"]:
                parts.append(f"localisation={msg['localisation']}")
            
            parsed_text = " ".join(parts)
            self.queue.put(('speech', parsed_text))
        
        def on_gesture_message(self, src, gesture, score):
            """Traite les messages de reconnaissance gestuelle"""
            print(f"[Ivy] Gesture received: {gesture} (score: {score})")
            self.queue.put(('gesture', gesture))

# --- Contrôleur de dialogue ---
class DialogueController:
    def __init__(self):
        self.state = DialogState.IDLE
        self.fusion_data = FusionData()
        self.formes = []
        self.last_clicked_forme = None
        self.app = None  # Référence à l'app pour pouvoir quitter
        
    def set_app(self, app):
        """Définit la référence à l'application"""
        self.app = app
    
    def update_mouse_position(self, position):
        """Met à jour la position de la souris pour les commandes"""
        self.fusion_data.add_mouse_position(position)
    
    def get_forme_at_position(self, position):
        """Trouve la forme sous une position donnée"""
        for forme in self.formes:
            if forme.is_clicked(position):
                return forme
        return None
        
    def process_speech(self, parsed_text):
        """Traite une commande vocale et met à jour la fusion"""
        # Parse le format SRA5: "action=CREATE form=CIRCLE color=RED localisation=THERE"
        parsed = {}
        for part in parsed_text.split():
            if '=' in part:
                key, value = part.split('=', 1)
                parsed[key] = value
        
        self.fusion_data.add_speech_info(parsed)
        print(f"[Speech] Added: {parsed}")
        print(f"[Fusion] {self.fusion_data}")
        
        self.update_state()
    
    def process_gesture(self, gesture_name):
        """Traite un geste reconnu"""
        self.fusion_data.add_gesture_info(gesture_name)
        print(f"[Gesture] Added: {gesture_name}")
        print(f"[Fusion] {self.fusion_data}")
        
        self.update_state()
    
    def process_click(self, position):
        """Traite un clic souris"""
        self.fusion_data.add_click_info(position)
        
        # Trouver la forme cliquée
        clicked = None
        for forme in self.formes:
            if forme.is_clicked(position):
                clicked = forme
                self.last_clicked_forme = forme
                break
        
        print(f"[Click] Position: {position}, Forme: {clicked.get_type() if clicked else 'None'}")
        print(f"[Fusion] {self.fusion_data}")
        
        self.update_state()
    
    def update_state(self):
        """Met à jour l'état du contrôleur et exécute les actions si possible"""
        
        # Vérifier timeout
        if self.fusion_data.is_expired():
            print("[Fusion] TIMEOUT - Réinitialisation")
            self.fusion_data.reset()
            self.state = DialogState.IDLE
            return
        
        # Vérifier QUIT
        if self.fusion_data.is_complete_quit():
            self.execute_quit()
            self.fusion_data.reset()
            self.state = DialogState.IDLE
            return
        
        # Vérifier DELETE
        if self.fusion_data.is_complete_delete():
            self.execute_delete()
            self.fusion_data.reset()
            self.state = DialogState.IDLE
            return
        
        # Vérifier CREATE
        if self.fusion_data.is_complete_create():
            self.execute_create()
            self.fusion_data.reset()
            self.state = DialogState.IDLE
            return
        
        # Vérifier MOVE
        if self.fusion_data.is_complete_move():
            self.execute_move()
            self.fusion_data.reset()
            self.state = DialogState.IDLE
            return
        
        # Mise à jour de l'état d'attente
        if self.fusion_data.action == "CREATE":
            if not self.fusion_data.shape:
                self.state = DialogState.WAITING_SHAPE
            elif self.fusion_data.deictic_location and not self.fusion_data.click_position:
                self.state = DialogState.WAITING_LOCATION
            else:
                self.state = DialogState.WAITING_LOCATION
        
        elif self.fusion_data.action == "MOVE":
            if self.fusion_data.deictic_location and not self.fusion_data.click_position:
                self.state = DialogState.WAITING_MOVE_DEST
            else:
                self.state = DialogState.WAITING_MOVE_DEST
        
        elif self.fusion_data.action == "DELETE":
            if self.fusion_data.deictic_location and not self.fusion_data.click_position:
                self.state = DialogState.WAITING_LOCATION
    
    def execute_create(self):
        """Exécute la création d'une forme"""
        # Déterminer la position
        if self.fusion_data.deictic_location and self.fusion_data.click_position:
            pos = self.fusion_data.click_position
        else:
            pos = (WIDTH // 2, HEIGHT // 2)
        
        # Déterminer la couleur
        color = DEFAULT_COLOR
        if self.fusion_data.color == 'SELECT':
            # Prendre la couleur de la forme sous la souris
            if self.fusion_data.mouse_position:
                forme_sous_souris = self.get_forme_at_position(self.fusion_data.mouse_position)
                if forme_sous_souris:
                    color = forme_sous_souris.color
                    print(f"[CREATE] Couleur SELECT détectée: {color}")
        elif self.fusion_data.color:
            color = COLORS.get(self.fusion_data.color, DEFAULT_COLOR)
        
        # Créer la forme
        shape_type = self.fusion_data.shape
        if shape_type == "CIRCLE":
            forme = Cercle(pos, color)
        elif shape_type == "RECTANGLE":
            forme = Rectangle(pos, color)
        elif shape_type == "TRIANGLE":
            forme = Triangle(pos, color)
        elif shape_type == "DIAMOND":
            forme = Losange(pos, color)
        else:
            return
        
        self.formes.append(forme)
        print(f"[Action] Created {shape_type} at {pos} with color {color}")
    
    def execute_move(self):
        """Exécute le déplacement d'une forme"""
        target_forme = None
        
        # CAS 1: MOVE THIS THERE - déplacer l'objet sous la souris
        if self.fusion_data.deictic_target and self.fusion_data.mouse_position:
            target_forme = self.get_forme_at_position(self.fusion_data.mouse_position)
            if target_forme:
                print(f"[MOVE] Forme THIS détectée: {target_forme.get_type()}")
        
        # CAS 2: MOVE CIRCLE THERE - déplacer par type de forme (sans couleur)
        elif self.fusion_data.shape and not self.fusion_data.color:
            for forme in self.formes:
                if forme.get_type() == self.fusion_data.shape:
                    target_forme = forme
                    print(f"[MOVE] Forme trouvée par type: {target_forme.get_type()}")
                    break
        
        # CAS 3: MOVE CIRCLE YELLOW THERE - déplacer par type ET couleur
        elif self.fusion_data.shape and self.fusion_data.color:
            target_color = COLORS.get(self.fusion_data.color, DEFAULT_COLOR)
            for forme in self.formes:
                if forme.get_type() == self.fusion_data.shape and forme.color == target_color:
                    target_forme = forme
                    print(f"[MOVE] Forme trouvée par type+couleur: {target_forme.get_type()}")
                    break
        
        # Déplacer vers la destination
        if target_forme and self.fusion_data.deictic_location and self.fusion_data.click_position:
            target_forme.set_location(self.fusion_data.click_position)
            print(f"[Action] Moved {target_forme.get_type()} to {self.fusion_data.click_position}")
        elif target_forme:
            print(f"[Action] Found {target_forme.get_type()} but no destination specified")
    
    def execute_delete(self):
        """Exécute la suppression - DELETE efface tout, DELETE THERE efface l'objet cliqué"""
        if not self.fusion_data.deictic_location:
            # DELETE sans localisation = tout effacer
            count = len(self.formes)
            self.formes.clear()
            print(f"[Action] Deleted all {count} shapes")
        else:
            # DELETE avec localisation = effacer l'objet cliqué
            if self.fusion_data.click_position:
                for forme in self.formes[:]:
                    if forme.is_clicked(self.fusion_data.click_position):
                        self.formes.remove(forme)
                        print(f"[Action] Deleted {forme.get_type()} at {self.fusion_data.click_position}")
                        break
    
    def execute_quit(self):
        """Exécute la fermeture de l'application"""
        print("[Action] QUIT - Fermeture de l'application")
        if self.app:
            self.app.running = False

# --- Application principale ---
class MultimodalPaletteApp:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Moteur de Fusion Multimodale - SRI 5A")
        
        self.controller = DialogueController()
        self.controller.set_app(self)  # Donner la référence pour QUIT
        self.clock = pygame.time.Clock()
        self.running = True
        
        # Drag and drop
        self.dragging = False
        self.dragged_forme = None
        self.drag_offset = (0, 0)
        
        # Position de la souris pour l'affichage
        self.mouse_pos = (0, 0)
        
        # File pour les messages Ivy
        self.message_queue = Queue()
        
        # Initialiser Ivy si disponible
        if IVY_AVAILABLE:
            self.ivy = IvyListener(self.message_queue)
            ivy_thread = Thread(target=self.start_ivy, daemon=True)
            ivy_thread.start()
            print("[Ivy] Started on 127.255.255.255:2010")
        else:
            self.ivy = None
            print("[Warning] Ivy not available - drag and drop only")
        
        self.font = pygame.font.SysFont('Arial', 18)
        self.small_font = pygame.font.SysFont('Arial', 14)
    
    def start_ivy(self):
        """Démarre Ivy dans un thread séparé"""
        self.ivy.start('127.255.255.255:2010')
    
    def draw_status(self):
        """Affiche le statut du système"""
        y = 10
        
        # État
        state_text = f"État: {self.controller.state}"
        state_surf = self.font.render(state_text, True, BLACK)
        self.screen.blit(state_surf, (10, y))
        y += 25
        
        # Mode drag
        if self.dragging:
            drag_text = f"Drag & Drop: {self.dragged_forme.get_type()}"
            drag_surf = self.font.render(drag_text, True, RED)
            self.screen.blit(drag_surf, (10, y))
            y += 25
        
        # Position souris (pour debug)
        mouse_text = f"Souris: {self.mouse_pos}"
        mouse_surf = self.small_font.render(mouse_text, True, GRAY)
        self.screen.blit(mouse_surf, (10, y))
        y += 20
        
        # Fusion data
        fd = self.controller.fusion_data
        if fd.action or fd.shape or fd.color:
            fusion_text = f"Fusion: action={fd.action or '?'} forme={fd.shape or '?'} couleur={fd.color or '?'}"
            fusion_surf = self.small_font.render(fusion_text, True, BLACK)
            self.screen.blit(fusion_surf, (10, y))
            y += 20
            
            if fd.deictic_location:
                deic_surf = self.small_font.render("En attente: cliquer pour la position", True, RED)
                self.screen.blit(deic_surf, (10, y))
                y += 20
        
        # Instructions
        y = HEIGHT - 200
        instructions = [
            "=== DRAG & DROP ===",
            "Cliquer et glisser une forme pour la déplacer",
            "",
            "=== COMMANDES MULTIMODALES (Ivy/SRA5) ===",
            "CREATE CIRCLE RED THERE → cliquer position",
            "CREATE CIRCLE SELECT THERE → prendre couleur sous souris + cliquer",
            "MOVE CIRCLE THERE → déplacer cercle (sans couleur) + cliquer",
            "MOVE CIRCLE YELLOW THERE → déplacer cercle jaune + cliquer",
            "MOVE THIS THERE → pointer souris sur objet + cliquer destination",
            "DELETE → efface tout",
            "DELETE THERE → cliquer sur objet à effacer",
            "QUIT → ferme la palette"
        ]
        for inst in instructions:
            inst_surf = self.small_font.render(inst, True, GRAY if inst else WHITE)
            self.screen.blit(inst_surf, (10, y))
            y += 16
    
    def run(self):
        """Boucle principale"""
        while self.running:
            self.screen.fill(WHITE)
            self.mouse_pos = pygame.mouse.get_pos()
            
            # Mettre à jour la position de la souris dans le contrôleur
            self.controller.update_mouse_position(self.mouse_pos)
            
            # Traiter les messages Ivy
            while not self.message_queue.empty():
                msg_type, msg_data = self.message_queue.get()
                if msg_type == 'speech':
                    self.controller.process_speech(msg_data)
                elif msg_type == 'gesture':
                    self.controller.process_gesture(msg_data)
            
            # Traiter les événements pygame
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    pos = pygame.mouse.get_pos()
                    
                    # Vérifier si on commence un drag
                    clicked_forme = None
                    for forme in self.controller.formes:
                        if forme.is_clicked(pos):
                            clicked_forme = forme
                            break
                    
                    if clicked_forme and not (self.controller.fusion_data.action or 
                                              self.controller.fusion_data.shape or 
                                              self.controller.fusion_data.gesture):
                        # Mode drag and drop simple (pas de fusion en cours)
                        self.dragging = True
                        self.dragged_forme = clicked_forme
                        self.drag_offset = (clicked_forme.x - pos[0], clicked_forme.y - pos[1])
                        print(f"[Drag] Started dragging {clicked_forme.get_type()}")
                    else:
                        # Mode fusion multimodale
                        self.controller.process_click(pos)
                
                elif event.type == pygame.MOUSEBUTTONUP:
                    if self.dragging:
                        print(f"[Drag] Dropped {self.dragged_forme.get_type()} at ({self.dragged_forme.x}, {self.dragged_forme.y})")
                        self.dragging = False
                        self.dragged_forme = None
                
                elif event.type == pygame.MOUSEMOTION:
                    if self.dragging and self.dragged_forme:
                        pos = pygame.mouse.get_pos()
                        self.dragged_forme.set_location((pos[0] + self.drag_offset[0], 
                                                        pos[1] + self.drag_offset[1]))
            
            # Afficher les formes
            for forme in self.controller.formes:
                # Highlight de la forme en cours de drag
                if self.dragging and forme == self.dragged_forme:
                    # Dessiner un contour
                    pygame.draw.circle(self.screen, RED, (int(forme.x), int(forme.y)), 45, 2)
                forme.draw(self.screen)
            
            # Afficher le statut
            self.draw_status()
            
            pygame.display.flip()
            self.clock.tick(60)
        
        # Cleanup
        if self.ivy:
            self.ivy.stop()
        pygame.quit()
        sys.exit()

# --- Point d'entrée ---
if __name__ == "__main__":
    app = MultimodalPaletteApp()
    app.run()