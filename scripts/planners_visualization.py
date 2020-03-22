from collections import defaultdict
import gym
from pathlib import Path
import itertools
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import seaborn as sns
import logging

from rl_agents.agents.tree_search.graphics import TreePlot
from rl_agents.agents.common.factory import agent_factory, load_environment
from rl_agents.trainer.logger import configure
from utils.envs import GridEnv

sns.set()
logger = logging.getLogger(__name__)

out = Path("out/planners")
gamma = 0.95

envs = {
    "highway": Path("configs") / "HighwayEnv" / "env.json",
    "bandit": Path("configs") / "FiniteMDPEnv" / "env_bandit.json",
    "env_loop": Path("configs") / "FiniteMDPEnv" / "env_loop.json",
    "env_garnet": Path("configs") / "FiniteMDPEnv" / "env_garnet.json",
    "gridenv": Path("configs") / "DummyEnv" / "gridenv.json",
    "gridenv-stoch": Path("configs") / "DummyEnv" / "gridenv-stoch.json",
    "dynamics": Path("configs") / "DummyEnv" / "dynamics.json",
}

agents = {
    "olop": {
        "__class__": "<class 'rl_agents.agents.tree_search.olop.OLOPAgent'>",
        "gamma": gamma,
        "upper_bound": {
            "type": "hoeffding",
            "c": 4
        },
        "lazy_tree_construction": True,
        "continuation_type": "uniform",
    },
    "kl-olop": {
        "__class__": "<class 'rl_agents.agents.tree_search.olop.OLOPAgent'>",
        "gamma": gamma,
        "upper_bound": {
            "type": "kullback-leibler",
            "threshold": "2*np.log(time) + 2*np.log(np.log(time))"
        },
        "lazy_tree_construction": True,
        "continuation_type": "uniform",
    },
    "KL-OLOP": {
        "__class__": "<class 'rl_agents.agents.tree_search.olop.OLOPAgent'>",
        "gamma": gamma,
        "upper_bound": {
            "type": "kullback-leibler",
            "threshold": "1*np.log(time)"
        },
        "lazy_tree_construction": True,
        "continuation_type": "uniform",
    },
    "laplace": {
        "__class__": "<class 'rl_agents.agents.tree_search.olop.OLOPAgent'>",
        "gamma": gamma,
        "upper_bound": {
            "type": "laplace",
            "c": 2
        },
        "lazy_tree_construction": True,
        "continuation_type": "uniform",
    },
    "OPD": {
        "__class__": "<class 'rl_agents.agents.tree_search.deterministic.DeterministicPlannerAgent'>",
        "gamma": gamma,
    },
    "state_aware": {
        "__class__": "<class 'rl_agents.agents.tree_search.state_aware.StateAwarePlannerAgent'>",
        "gamma": gamma,
        "backup_aggregated_nodes": True,
        "prune_suboptimal_leaves": True,
        "stopping_accuracy": 1e-1
    },
    "GBOP-D": {
        "__class__": "<class 'rl_agents.agents.tree_search.graph_based.GraphBasedPlannerAgent'>",
        "gamma": gamma,
    },
    "GBOP": {
        "__class__": "<class 'rl_agents.agents.tree_search.graph_based_stochastic.StochasticGraphBasedPlannerAgent'>",
        "gamma": gamma,
        "upper_bound":
        {
            "type": "kullback-leibler",
            "threshold": "0*np.log(time)",
            "transition_threshold": "0*np.log(time)"
        },
    },
    "MDP-GapE": {
        "__class__": "<class 'rl_agents.agents.tree_search.mdp_gape.MDPGapEAgent'>",
        "gamma": gamma,
        "accuracy": 0,
        "confidence": 1,
        "upper_bound":
        {
            "type": "kullback-leibler",
            "time": "global",
            "threshold": "0*np.log(time)",
            "transition_threshold": "0*np.log(time)"
        },
        "max_next_states_count": 1,
        "continuation_type": "uniform",
        "step_strategy": "reset",
    },
}


def evaluate(env, agent_name, budget, seed=None):
    print("Evaluating", agent_name, "with budget", budget)
    agent_config = agents[agent_name]
    agent_config["budget"] = budget
    agent = agent_factory(env, agent_config)
    if seed is not None:
        env.seed(seed)
        agent.seed(seed)
    obs = env.reset()
    agent.act(obs)
    return agent


def evaluate_agents(env, agents, budget, seed=None):
    for agent_name in agents.keys():
        agent = evaluate(env, agent_name, budget, seed=seed)
        yield agent, agent_name


def compare_agents(env, agents, budget, seed=None, show_tree=False, show_trajs=False, show_states=False):
    trajectories = {}
    state_occupations = {}
    state_updates = {}
    state_limits = 20
    for agent, agent_name in evaluate_agents(env, agents, budget, seed):
        trajectories[agent_name] = agent.planner.root.get_trajectories(env)
        # Aggregate visits
        visits, updates = agent.planner.root.get_obs_visits(state=env)

        if isinstance(env, GridEnv):
            state_occupations[agent_name] = np.zeros((2 * state_limits + 1, 2 * state_limits + 1))
            state_updates[agent_name] = np.zeros((2 * state_limits + 1, 2 * state_limits + 1))
            for i, x in enumerate(np.arange(-state_limits, state_limits)):
                for j, y in enumerate(np.arange(-state_limits, state_limits)):
                    state_occupations[agent_name][i, j] = visits[str(np.array([x, y]))]
                    state_updates[agent_name][i, j] = updates[str(np.array([x, y]))]

        if show_tree:
            TreePlot(agent.planner, max_depth=100).plot(out / "{}.pdf".format(agent_name), title=agent_name)
            plt.show()

    if show_states:
        v_max = max([st.max() for st in state_occupations.values()] + [0])
        if v_max > 0:
            for agent_name, occupations in state_occupations.items():
                show_state_map("occupations", agent_name, occupations, state_limits, v_max)
        # v_max = max([st.max() for st in state_updates.values()] + [0])
        # if v_max > 0:
        #     for agent_name, updates in state_updates.items():
        #         show_state_map("updates", agent_name, updates, state_limits, v_max)

    if show_trajs:
        axes = None
        palette = itertools.cycle(sns.color_palette())
        for agent_name, agent_trajectories in trajectories.items():
            axes = show_trajectories(agent_name, agent_trajectories, axes=axes, color=next(palette))
        plt.show()
        plt.savefig(out / "trajectories.png")


def show_state_map(title, agent_name, values, state_limits, v_max=None):
    fig, ax = plt.subplots()
    img = ax.imshow(values.T,
                    extent=(-state_limits, state_limits, -state_limits, state_limits),
                    norm=colors.SymLogNorm(linthresh=1, linscale=1, vmax=v_max),
                    cmap=plt.cm.coolwarm)
    fig.colorbar(img, ax=ax)
    plt.grid(False)
    plt.title(agent_name)
    plt.savefig(out / "{}_{}.pdf".format(title, agent_name))
    plt.show()


def show_trajectories(agent_name, trajectories, axes=None, color=None):
    if not axes:
        fig, axes = plt.subplots()
        for trajectory in trajectories:
            x, y = zip(*trajectory.observation)
            plt.plot(x, y, linestyle='dotted', linewidth=0.5, label=agent_name, color=color)
    return axes


if __name__ == "__main__":
    configure("configs/logging.json", gym_level=gym.logger.INFO)
    selected_env = load_environment(envs["gridenv"])
    selected_agents = [
         "OPD",
         "GBOP-D",
         # "KL-OLOP",
         "MDP-GapE",
         "GBOP",
    ]
    selected_agents = {k: v for k, v in agents.items() if k in selected_agents}
    budget = 4 * (4 ** 6 - 1) / (4 - 1)
    # budget = 200
    compare_agents(selected_env, selected_agents, budget=budget,
                   show_tree=True, show_states=True, show_trajs=False, seed=0)
