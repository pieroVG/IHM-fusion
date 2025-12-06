import pygame
import sys
import threading
import unicodedata
import math
from queue import Queue
import speech_recognition as sr
import time

# ------------------------------
# CONFIGURATION
# ------------------------------
pygame.init()

WIDTH, HEIGHT = 800, 600
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
COLORS = {
    "rouge": RED,
    "vert": GREEN,
    "bleu": BLUE,
    "jaune": YELLOW,
    "noir": BLACK,
    "blanc": WHITE
}

PALETTE_HEIGHT = 50
COLOR_BOX_SIZE = 40
COLOR_MARGIN = 10

ETAT_ATTENTE = "ATTENTE"
ETAT_DEPLACEMENT = "DEPLACEMENT"

AUTO_DROP_DELAY = 0.5

# ------------------------------
# OUTILS
# ------------------------------
def normaliser(texte):
    if not texte:
        return ""
    texte = unicodedata.normalize('NFD', texte)
    texte = ''.join(c for c in texte if unicodedata.category(c) != 'Mn')
    return texte.lower()

def assombrir(c):
    return tuple(max(v - 70, 0) for v in c)

# ------------------------------
# FORMES
# ------------------------------
class Forme:
    def __init__(self, x, y, color=WHITE):
        self.x = x
        self.y = y
        self.color = color

    def set_location(self, x, y):
        self.x, self.y = x, y

    def set_color(self, color):
        self.color = color

    def distance_to(self, pos):
        return ((self.x - pos[0]) ** 2 + (self.y - pos[1]) ** 2) ** 0.5

    def draw(self, screen):
        pass

class Cercle(Forme):
    radius = 30
    def draw(self, screen):
        pygame.draw.circle(screen, self.color, (self.x, self.y), self.radius)

class Rectangle(Forme):
    width = 60
    height = 40
    def draw(self, screen):
        pygame.draw.rect(screen, self.color,
                         (self.x - self.width // 2, self.y - self.height // 2,
                          self.width, self.height))

class Triangle(Forme):
    size = 50
    def draw(self, screen):
        points = [
            (self.x, self.y - self.size),
            (self.x + self.size, self.y + self.size),
            (self.x - self.size, self.y + self.size)
        ]
        pygame.draw.polygon(screen, self.color, points)

class Losange(Forme):
    size = 50
    def draw(self, screen):
        points = [
            (self.x, self.y - self.size),
            (self.x + self.size, self.y),
            (self.x, self.y + self.size),
            (self.x - self.size, self.y)
        ]
        pygame.draw.polygon(screen, self.color, points)

# ------------------------------
# ÉCOUTE VOCALE
# ------------------------------
def ecouter_thread(queue):
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            while True:
                try:
                    audio = recognizer.listen(source, timeout=1, phrase_time_limit=3)
                    txt = recognizer.recognize_google(audio, language="fr-FR")
                    queue.put(normaliser(txt))
                except sr.WaitTimeoutError:
                    pass
                except sr.UnknownValueError:
                    pass
                except sr.RequestError:
                    pass
    except:
        pass

# ------------------------------
# $1 Recognizer minimal
# ------------------------------
class DollarOneRecognizer:
    def __init__(self):
        self.templates = {}
    
    def add_template(self, name, points):
        self.templates[name] = self.resample(points)
    
    def resample(self, points, n=64):
        if len(points) < 2:
            return points
        total_len = sum(math.dist(points[i], points[i+1]) for i in range(len(points)-1))
        D = total_len / (n-1)
        new_points = [points[0]]
        d = 0
        for i in range(1, len(points)):
            dist = math.dist(points[i-1], points[i])
            if (d + dist) >= D:
                t = (D - d) / dist
                x = points[i-1][0] + t*(points[i][0]-points[i-1][0])
                y = points[i-1][1] + t*(points[i][1]-points[i-1][1])
                new_points.append((x, y))
                points.insert(i, (x, y))
                d = 0
            else:
                d += dist
        while len(new_points) < n:
            new_points.append(points[-1])
        return new_points

    def recognize(self, points):
        points = self.resample(points)
        best_score = float('inf')
        best_name = None
        for name, template in self.templates.items():
            score = sum(math.dist(points[i], template[i]) for i in range(len(points)))
            if score < best_score:
                best_score = score
                best_name = name
        return best_name

# ------------------------------
# PROGRAMME PRINCIPAL
# ------------------------------
def main():
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Palette + $1 Recognizer + Voice")

    forme_courante = None
    couleur_originale = None
    couleur_courante = BLACK
    formes = []
    etat = ETAT_ATTENTE

    drawing = False
    drawing_points = []

    commande_queue = Queue()
    t = threading.Thread(target=ecouter_thread, args=(commande_queue,))
    t.daemon = True
    t.start()

    recognizer = DollarOneRecognizer()
    recognizer.add_template("cercle", [(math.cos(t)*50+400, math.sin(t)*50+300) for t in [i*2*math.pi/32 for i in range(32)]])
    recognizer.add_template("rectangle", [(350,250),(450,250),(450,350),(350,350)])
    recognizer.add_template("triangle", [(400,250),(450,350),(350,350)])
    recognizer.add_template("losange", [(400,250),(450,300),(400,350),(350,300)])

    last_mouse_move_time = time.time()

    running = True
    while running:
        screen.fill(WHITE)
        current_mouse_pos = pygame.mouse.get_pos()
        mouse_moved = (pygame.mouse.get_rel() != (0,0))
        if mouse_moved:
            last_mouse_move_time = time.time()

        # ------------------------------
        # Affichage bandeau palette
        # ------------------------------
        palette_rects = {}
        x_offset = COLOR_MARGIN
        for nom, col in COLORS.items():
            rect = pygame.Rect(x_offset, COLOR_MARGIN, COLOR_BOX_SIZE, COLOR_BOX_SIZE)
            pygame.draw.rect(screen, col, rect)
            if col == couleur_courante:
                pygame.draw.rect(screen, BLACK, rect, 3)
            palette_rects[nom] = rect
            x_offset += COLOR_BOX_SIZE + COLOR_MARGIN

        # ------------------------------
        # Gestion événements
        # ------------------------------
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Clique sur palette ?
                clicked_on_palette = False
                for nom, rect in palette_rects.items():
                    if rect.collidepoint(event.pos):
                        couleur_courante = COLORS[nom]
                        clicked_on_palette = True
                        break
                if not clicked_on_palette and event.pos[1] > PALETTE_HEIGHT:
                    drawing = True
                    drawing_points = [event.pos]

            elif event.type == pygame.MOUSEMOTION and drawing:
                drawing_points.append(event.pos)

            elif event.type == pygame.MOUSEBUTTONUP and event.button == 1 and drawing:
                drawing = False
                if len(drawing_points) > 1:
                    shape_name = recognizer.recognize(drawing_points)
                    xs = [p[0] for p in drawing_points]
                    ys = [p[1] for p in drawing_points]
                    center = (sum(xs)//len(xs), sum(ys)//len(ys))
                    if shape_name == "cercle": formes.append(Cercle(*center, couleur_courante))
                    elif shape_name == "rectangle": formes.append(Rectangle(*center, couleur_courante))
                    elif shape_name == "triangle": formes.append(Triangle(*center, couleur_courante))
                    elif shape_name == "losange": formes.append(Losange(*center, couleur_courante))

        # ------------------------------
        # Gestion commandes vocales
        # ------------------------------
        while not commande_queue.empty():
            speech = commande_queue.get()
            if speech:
                print("Commande vocale :", speech)
                # Création
                if any(f in speech for f in ["cercle","rectangle","triangle","losange"]):
                    pos = current_mouse_pos if "ici" in speech else (WIDTH//2, HEIGHT//2)
                    if "cercle" in speech: forme_courante = Cercle(*pos)
                    elif "rectangle" in speech: forme_courante = Rectangle(*pos)
                    elif "triangle" in speech: forme_courante = Triangle(*pos)
                    elif "losange" in speech: forme_courante = Losange(*pos)
                    
                    # Applique la couleur vocale si elle est mentionnée
                    for nom, col in COLORS.items():
                        if nom in speech:
                            forme_courante.set_color(col)
                            break
                    else:
                        # Sinon couleur de la palette
                        forme_courante.set_color(couleur_courante)

                    formes.append(forme_courante)
                # Déplacement
                if "deplace ca" in speech or "déplace ça" in speech or "des places" in speech:
                    if formes:
                        forme_courante = min(formes, key=lambda f: f.distance_to(current_mouse_pos))
                        couleur_originale = forme_courante.color
                        forme_courante.set_color(assombrir(couleur_originale))
                        etat = ETAT_DEPLACEMENT
                        last_mouse_move_time = time.time()
                # Pose vocale
                if etat == ETAT_DEPLACEMENT and speech == "la":
                    forme_courante.set_location(*current_mouse_pos)
                    forme_courante.set_color(couleur_originale)
                    forme_courante = None
                    etat = ETAT_ATTENTE
                # Quitter
                if "quitter" in speech:
                    running = False

        # ------------------------------
        # Déplacement souris (mode drag)
        # ------------------------------
        if etat == ETAT_DEPLACEMENT and forme_courante:
            forme_courante.set_location(*current_mouse_pos)
            if time.time() - last_mouse_move_time > AUTO_DROP_DELAY:
                forme_courante.set_color(couleur_originale)
                forme_courante = None
                etat = ETAT_ATTENTE

        # ------------------------------
        # Affichage dessin temporaire
        # ------------------------------
        if drawing and len(drawing_points) > 1:
            pygame.draw.lines(screen, couleur_courante, False, drawing_points, 3)

        # ------------------------------
        # Affichage formes
        # ------------------------------
        for f in formes:
            f.draw(screen)

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
