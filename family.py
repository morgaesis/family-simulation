""" A simulation of the Family Inc. game to find the optimal strategy """

# pylint: disable=too-few-public-methods
# pylint: disable=invalid-name

import random
import logging
import multiprocessing
from abc import abstractmethod


class ChipPool:
    """Pool of chips at center of table"""

    def __init__(self, players):
        self.chips = {}
        self.players = players
        self.reset()

    def reset(self):
        """Reset the pile for a new game"""
        self.chips = {i: (15 if i < 6 else 11) for i in range(1, 11)}

    def draw(self):
        """Draw a chip and give to the player"""
        if sum(self.chips.values()) == 0:
            logging.debug("Pile is empty!")
            logging.debug("Making a new centre pile")
            self.chips = {i: (15 if i < 6 else 11) for i in range(1, 11)}
            for player in self.players:
                for k, v in player.chips.items():
                    self.chips[k] -= v
        chip = random.choices(range(1, 11), weights=self.chips.values())[0]
        self.chips[chip] -= 1
        return chip


class Player:
    """A basic player, drawing only once each time"""

    def __init__(self, name, players=None):
        self.name = name
        self.players = players
        self.chips = {}
        self.diamonds = 0
        self.score = 0
        self.drawn_chips = 0
        self.has_won = False
        self.reset()

    def reset(self):
        """Reset Player for a new game"""
        self.diamonds = 0
        self.score = 0
        self.drawn_chips = 0
        self.has_won = False
        self.reset_chips()

    def reset_chips(self):
        """Throw away all chips"""
        for chip in range(1, 11):
            self.chips[chip] = 0

    @abstractmethod
    def will_draw(self):
        """Logic for whether or not to draw more"""
        raise NotImplementedError()

    def calc_stealable(self):
        """Calculate the amount in all player hands able to steal"""
        stealable = 0
        for player in self.players:
            if player == self:
                continue
            stealable += sum([k * v for k, v in player.chips.items()])
        return stealable

    def to_be_stolen(self):
        """Calculate how much is about to be stolen if player decides to stop drawing"""
        stolen = 0
        for player in self.players:
            if player == self:
                continue
            stolen += sum([k * v for k, v in player.chips.items() if k in self.chips])
        return stolen

    def step1(self):
        """Step 1 in player's turn"""
        advance = 0
        if self.diamonds == 3:
            logging.debug("%s has 3 diamonds and anvances 50", self.name)
            self.diamonds = 0
            advance += 50
        for k, v in self.chips.items():
            advance += k * v
        self.reset_chips()
        self.score += advance
        if advance > 0:
            logging.debug(
                "%s advances %s to %s",
                self.name,
                advance,
                self.score,
            )
        else:
            logging.debug("%s doesn't advance", self.name)
        if self.score >= 100:
            logging.debug(
                "%s has gotten a score greater than 100 and has WON!", self.name
            )
            self.has_won = True

    def step2(self, pool):
        """Step 2 in player's turn"""
        self.drawn_chips = 0
        while self.will_draw():
            chip = pool.draw()
            self.drawn_chips += 1
            logging.debug("%s drew %d", self.name, chip)
            if self.chips[chip] > 0:
                logging.debug("%s already has %d!", self.name, chip)
                if self.drawn_chips <= 3:
                    self.diamonds += 1
                    logging.debug(
                        "%s gets a diamond (has now %d diamonds)",
                        self.name,
                        self.diamonds,
                    )
                    # f"{self.name} gets a diamond (has now {self.diamonds} diamonds)"
                self.reset_chips()
                return
            self.chips[chip] += 1

    def step3(self, players):
        """Step 3 in player's turn"""
        robbing_chips = [k for k, v in self.chips.items() if v > 0]
        for player in players:
            if player == self:
                continue
            for chip in robbing_chips:
                stolen = player.chips[chip]
                if stolen > 0:
                    logging.debug(
                        "%s steals %d %ds from %s",
                        self.name,
                        stolen,
                        chip,
                        player.name,
                    )
                    # f"{self.name} steals {stolen} {chip}s from {player.name}"
                self.chips[chip] += stolen
                player.chips[chip] = 0


class InteractivePlayer(Player):
    """Interactive CLI player"""

    def will_draw(self):
        """Logic for whether to draw"""
        if input(f"{self.name}, will you draw a chip? [Y/n] ").lower() == "n":
            return False
        return True


class RandomPlayer(Player):
    """AI randomly drawing"""

    def __init__(self, name, r=0.5, **common):
        self.r = r
        super().__init__(name, **common)

    def will_draw(self):
        """Draw at random, at chance self.r"""
        return random.random() < self.r


class ThresholdPlayer(Player):
    """AI based on threshold"""

    def __init__(self, name, n, **common):
        self.n = n
        super().__init__(name, **common)

    def will_draw(self):
        """
        Logic for whether to draw

        self.n is the maximum number of chips the player wants to have,
        i.e. draw if their number of chips is less than self.n
        """
        return self.drawn_chips < self.n


class ConservativePlayer(Player):
    """AI only taking until satisfied (or hits drawn chips)"""

    def __init__(self, name, satisfaction, n, **common):
        self.n = n
        self.satisfaction = satisfaction
        super().__init__(name, **common)

    def will_draw(self):
        """
        Never draw more than self.n
        Draw if to-be-stolen < self.satisfaction
        """
        if self.drawn_chips < self.n:
            return True
        return self.to_be_stolen() < self.satisfaction


class GreedyPlayer(Player):
    """AI based on threshold and number of stealable chips"""

    def __init__(self, name, stealable, stolen, n=None, **common):
        self.n = n
        self.stealable = stealable
        self.stolen = stolen
        super().__init__(name, **common)

    def will_draw(self):
        """
        Draw a maximum of self.n chips.
        Draw if sum of stealable chips > self.stealable.
        If stealable chips is less than self.stealable, draw until self.stolen
        has been stolen.
        """
        if self.n and self.drawn_chips < self.n:
            return True
        if self.calc_stealable() > self.stealable:
            return True
        if self.to_be_stolen() < self.stolen:
            return True
        return False


def game(players):
    """One game"""
    pool = ChipPool(players)
    game_over = False
    winner = None

    while not game_over:
        for player in players:
            if game_over:
                break
            player.step1()
            if player.has_won:
                winner = player
                logging.debug("%s has won the game!", player.name)
                game_over = True
                break
            player.step2(pool)
            player.step3(players)

    logging.debug("\n=========\nGAME OVER\n=========")

    return winner


def experiment(n_players, N):
    """experiment loop"""
    instantiations = [
        [ThresholdPlayer, ("Threshold-1", 1)],
        [ThresholdPlayer, ("Threshold-2", 2)],
        [ThresholdPlayer, ("Threshold-3", 3)],
        [ThresholdPlayer, ("Threshold-4", 4)],
        [ThresholdPlayer, ("Threshold-5", 5)],
        [ThresholdPlayer, ("Threshold-6", 6)],
        [ThresholdPlayer, ("Threshold-7", 7)],
        [ThresholdPlayer, ("Threshold-8", 8)],
        [RandomPlayer, ("Random-0.5", 0.5)],
        [RandomPlayer, ("Random-0.6", 0.6)],
        [RandomPlayer, ("Random-0.7", 0.7)],
        [RandomPlayer, ("Random-0.8", 0.8)],
        [RandomPlayer, ("Random-0.9", 0.9)],
        [RandomPlayer, ("Random-0.95", 0.95)],
        [GreedyPlayer, ("Greedy-1", 5, 5)],
        [GreedyPlayer, ("Greedy-2", 10, 10, 4)],
        [GreedyPlayer, ("Greedy-3", 15, 15, 4)],
        [GreedyPlayer, ("Greedy-4", 20, 20, 4)],
        [GreedyPlayer, ("Greedy-5", 30, 30, 4)],
        [GreedyPlayer, ("Greedy-6", 40, 40, 4)],
        [ConservativePlayer, ("Conservative-10", 10, 3)],
        [ConservativePlayer, ("Conservative-20", 20, 3)],
        [ConservativePlayer, ("Conservative-30", 30, 3)],
    ]
    winners = {i[1][0]: 0 for i in instantiations}
    participations = {i[1][0]: 0 for i in instantiations}
    for _ in range(N):
        weights = [random.randint(0, 10) for _ in instantiations]
        players = []
        for c, a in random.choices(
            instantiations,
            weights=weights,
            k=n_players,
        ):
            players.append(c(*a, players=players))

        logging.info("Weights: %s", weights)
        logging.info("players: %s", [p.name for p in players])
        for player in players:
            player.reset()

        winners[game(players).name] += 1
        for player in players:
            participations[player.name] += 1

    logging.warning("Experiment results for %d players, %d rounds", n_players, N)
    logging.warning("Base chance: %.2f%%", 1 / n_players * 100)
    logging.warning("Winner statistics:")
    win_rates = []
    for player, wins in winners.items():
        win_rate = wins / participations[player] * 100
        win_rates.append((win_rate, player))
    win_rates.sort()
    win_rates.reverse()
    for win_rate, player in win_rates:
        logging.warning("%s: %.2f%%", player, win_rate)
    logging.warning("========================\n")
    return win_rates


def main():
    """Main loop"""
    logging.basicConfig(format="%(message)s", level=logging.WARNING)
    args = [(n_players, 5000) for n_players in range(2, 8)]
    with multiprocessing.Pool() as p:
        p.starmap(experiment, args)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nBYE")
