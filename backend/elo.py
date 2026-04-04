K = 32


def expected_score(rating_a: float, rating_b: float) -> float:
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def update_elo(winner_rating: float, loser_rating: float) -> tuple[float, float]:
    expected_winner = expected_score(winner_rating, loser_rating)
    expected_loser = expected_score(loser_rating, winner_rating)
    new_winner = winner_rating + K * (1 - expected_winner)
    new_loser = loser_rating + K * (0 - expected_loser)
    return round(new_winner, 2), round(new_loser, 2)
