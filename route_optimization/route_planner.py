"""
RouteRanker: Route Planner Service
Computes optimal itineraries across the Chicago CTA transit network using transfer-aware Dijkstra optimization.
Strictly Chicago CTA data.
"""

import os
import joblib
import networkx as nx
import itertools
from typing import Dict, Any, List, Optional, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
DEFAULT_GRAPH_PATH = os.path.join(MODELS_DIR, "cta_network_graph.joblib")


class CTARoutePlanner:
    def __init__(self, graph_path: str = DEFAULT_GRAPH_PATH, transfer_penalty_minutes: float = 5.0):
        self._graph_path = graph_path
        self._transfer_penalty = float(transfer_penalty_minutes)
        self._graph = None
        self._graph_line = None

    def _load_graph(self):
        if self._graph is None:
            if not os.path.exists(self._graph_path):
                raise FileNotFoundError(f"Transit graph not found at {self._graph_path}")
            self._graph = joblib.load(self._graph_path)
            self._build_expanded_graph()

    def _build_expanded_graph(self):
        """
        Builds a line-aware dual transit graph where state is (station_node, line).
        Inter-line transitions within a station or via pedestrian pedways carry
        the configurable transfer penalty (default: 5.0 minutes) to prevent
        unnecessary transfers when a continuous direct route is available.
        """
        G = self._graph
        G_line = nx.DiGraph()

        # 1. Add transit track / route segment edges
        for u, v, d in G.edges(data=True):
            mode = d.get("mode", "Rail")
            line = d.get("line", "Unknown")
            w = float(d.get("weight", 2.0))
            dist = float(d.get("distance_miles", 0))

            if mode in ("Rail", "Bus"):
                G_line.add_edge(
                    (u, line),
                    (v, line),
                    weight=w,
                    pure_duration=w,
                    mode=mode,
                    line=line,
                    distance_miles=dist,
                    is_transfer=False,
                )
            elif mode in ("Transfer", "Walk"):
                u_lines = [ed["line"] for _, _, ed in G.in_edges(u, data=True)] + [
                    ed["line"] for _, _, ed in G.out_edges(u, data=True)
                ]
                v_lines = [ed["line"] for _, _, ed in G.in_edges(v, data=True)] + [
                    ed["line"] for _, _, ed in G.out_edges(v, data=True)
                ]
                pure_w = float(d.get("walk_duration_minutes", w))
                for ul in set(u_lines):
                    for vl in set(v_lines):
                        G_line.add_edge(
                            (u, ul),
                            (v, vl),
                            weight=w,
                            pure_duration=pure_w,
                            mode=mode,
                            line=line,
                            distance_miles=dist,
                            is_transfer=True,
                        )

        # 2. Add intra-station line transfer edges
        for n in G.nodes():
            lines = set(
                [ed["line"] for _, _, ed in G.in_edges(n, data=True)]
                + [ed["line"] for _, _, ed in G.out_edges(n, data=True)]
            )
            for l1 in lines:
                for l2 in lines:
                    if l1 != l2:
                        G_line.add_edge(
                            (n, l1),
                            (n, l2),
                            weight=self._transfer_penalty,
                            pure_duration=3.0,
                            mode="Transfer",
                            line=f"Transfer to {l2}",
                            distance_miles=0.0,
                            is_transfer=True,
                        )

        self._graph_line = G_line

    def plan_route(
        self,
        origin_id: str,
        destination_id: str,
        preference: str = "fastest",
        max_options: int = 3,
    ) -> Dict[str, Any]:
        """
        Plans a route between origin and destination stops.
        preference: 'fastest' (minimum journey duration) or 'min_transfers' (penalizes line changes heavily).
        """
        self._load_graph()
        G = self._graph
        G_line = self._graph_line

        src_candidates = self._find_candidate_node_ids(origin_id)
        dst_candidates = self._find_candidate_node_ids(destination_id)

        if not src_candidates:
            return {"error": f"Origin stop '{origin_id}' not found in Chicago transit network."}
        if not dst_candidates:
            return {"error": f"Destination stop '{destination_id}' not found in Chicago transit network."}

        # Weight multiplier for transfers when preference is min_transfers
        mult = 2.5 if preference == "min_transfers" else 1.0
        weight_func = lambda u, v, ed: ed["weight"] * (mult if ed.get("is_transfer") else 1.0)

        all_options = []
        seen = set()

        for s_base in src_candidates:
            s_nodes = [n for n in G_line.nodes() if n[0] == s_base]
            for d_base in dst_candidates:
                if s_base == d_base:
                    continue
                d_nodes = [n for n in G_line.nodes() if n[0] == d_base]
                for s in s_nodes:
                    for d in d_nodes:
                        try:
                            paths = list(
                                itertools.islice(
                                    nx.shortest_simple_paths(G_line, s, d, weight=weight_func),
                                    3,
                                )
                            )
                            for p in paths:
                                # Clean leading or trailing trivial intra-station transfers if they don't change transit line
                                if len(p) >= 2 and p[0][0] == p[1][0]:
                                    continue  # Skip redundant initial boarding transfer
                                if len(p) >= 2 and p[-1][0] == p[-2][0]:
                                    continue  # Skip redundant final arrival transfer
                                
                                st_seq = tuple(x[0] for x in p)
                                line_seq = tuple(x[1] for x in p)
                                key = (st_seq, line_seq)
                                if key not in seen:
                                    seen.add(key)
                                    penalized_cost = sum(
                                        weight_func(p[j], p[j + 1], G_line.edges[p[j], p[j + 1]])
                                        for j in range(len(p) - 1)
                                    )
                                    all_options.append((penalized_cost, p))
                        except Exception:
                            pass

        if not all_options:
            return {
                "error": f"No direct transit path found between '{origin_id}' and '{destination_id}'."
            }

        all_options.sort(key=lambda x: x[0])

        rec_p = all_options[0][1]
        recommended_itinerary = self._format_itinerary(rec_p, label="Recommended Route")

        # Select distinct alternative itineraries
        alternatives = []
        alt_count = 1
        seen_primary_lines = {rec_p[0][1]}
        seen_station_corridors = {tuple(x[0] for x in rec_p)}

        for _, p in all_options[1:]:
            st_corridor = tuple(x[0] for x in p)
            primary_line = p[0][1]
            # Avoid showing trivial variants that only add a transfer without offering a distinct corridor
            if st_corridor in seen_station_corridors and primary_line in seen_primary_lines:
                continue

            itin = self._format_itinerary(p, label=f"Alternative Route {alt_count}")
            # Ensure alternative offers a genuinely distinct option
            if (
                itin["total_duration_minutes"] != recommended_itinerary["total_duration_minutes"]
                or itin["transfers_count"] != recommended_itinerary["transfers_count"]
                or len(itin["itinerary_legs"]) != len(recommended_itinerary["itinerary_legs"])
            ):
                alternatives.append(itin)
                seen_primary_lines.add(primary_line)
                seen_station_corridors.add(st_corridor)
                alt_count += 1
                if alt_count >= max_options:
                    break

        src_node_id = rec_p[0][0]
        dst_node_id = rec_p[-1][0]

        return {
            "origin": {
                "id": src_node_id,
                "name": G.nodes[src_node_id]["name"],
                "descriptive_name": G.nodes[src_node_id].get(
                    "descriptive_name", G.nodes[src_node_id]["name"]
                ),
                "lines_served": G.nodes[src_node_id].get("lines_served", []),
                "latitude": G.nodes[src_node_id]["latitude"],
                "longitude": G.nodes[src_node_id]["longitude"],
            },
            "destination": {
                "id": dst_node_id,
                "name": G.nodes[dst_node_id]["name"],
                "descriptive_name": G.nodes[dst_node_id].get(
                    "descriptive_name", G.nodes[dst_node_id]["name"]
                ),
                "lines_served": G.nodes[dst_node_id].get("lines_served", []),
                "latitude": G.nodes[dst_node_id]["latitude"],
                "longitude": G.nodes[dst_node_id]["longitude"],
            },
            "preference_applied": preference,
            "recommended_itinerary": recommended_itinerary,
            "alternative_itineraries": alternatives,
            "disclaimer": (
                "Scheduled journey times are calculated from official CTA GTFS timetables. "
                "Actual transit times may vary with live traffic or dispatch headways."
            ),
        }

    def _find_candidate_node_ids(self, query: str) -> List[str]:
        G = self._graph
        q_clean = str(query).strip().lower()

        # Direct key match
        if query in G:
            return [query]
        if f"RAIL_{query}" in G:
            return [f"RAIL_{query}"]

        exact_matches = []
        partial_matches = []

        for node, data in G.nodes(data=True):
            s_name = data.get("name", "").lower()
            desc = data.get("descriptive_name", "").lower()
            sid = str(data.get("station_id", "")).lower()

            if q_clean == s_name or q_clean == desc or q_clean == sid:
                exact_matches.append(node)
            elif q_clean in s_name or q_clean in desc:
                partial_matches.append(node)

        if exact_matches:
            return exact_matches
        return partial_matches

    def _format_itinerary(self, path: List[Tuple[str, str]], label: str) -> Dict[str, Any]:
        G = self._graph
        G_line = self._graph_line

        total_duration = 0.0
        total_distance = 0.0
        legs = []
        transfers = 0
        current_leg = None
        waypoints = []

        for i in range(len(path) - 1):
            u_node, u_line = path[i]
            v_node, v_line = path[i + 1]
            edge_data = G_line.edges[path[i], path[i + 1]]
            u_data = G.nodes[u_node]
            v_data = G.nodes[v_node]

            pure_w = float(edge_data.get("pure_duration", edge_data["weight"]))
            dist = float(edge_data.get("distance_miles", 0.0))
            mode = edge_data.get("mode", "Rail")
            line = edge_data.get("line", u_line)

            total_duration += pure_w
            total_distance += dist
            waypoints.append([u_data["latitude"], u_data["longitude"]])

            if edge_data.get("is_transfer"):
                transfers += 1
                if current_leg:
                    legs.append(current_leg)
                    current_leg = None

                instruction = (
                    f"Transfer to {v_line} at {u_data['name']} (~{round(pure_w, 1)} min)"
                    if u_node == v_node
                    else f"Walk / Transfer from {u_data['name']} to {v_data['name']} (~{round(pure_w, 1)} min)"
                )

                legs.append({
                    "action": "Transfer / Walk",
                    "from_stop": u_data["name"],
                    "from_node": u_data["name"],
                    "to_stop": v_data["name"],
                    "to_node": v_data["name"],
                    "line": line,
                    "mode": mode,
                    "duration_minutes": round(pure_w, 1),
                    "estimated_minutes": round(pure_w, 1),
                    "stops_count": 1,
                    "instruction": instruction,
                })
                continue

            if current_leg is None:
                current_leg = {
                    "action": f"Board {mode}",
                    "line": line,
                    "mode": mode,
                    "from_stop": u_data["name"],
                    "from_node": u_data["name"],
                    "to_stop": v_data["name"],
                    "to_node": v_data["name"],
                    "stops_count": 1,
                    "duration_minutes": pure_w,
                    "estimated_minutes": round(pure_w, 1),
                    "instruction": f"Board {line} Line at {u_data['name']}",
                }
            elif current_leg["line"] == line:
                current_leg["stops_count"] += 1
                current_leg["duration_minutes"] += pure_w
                current_leg["estimated_minutes"] = round(current_leg["duration_minutes"], 1)
                current_leg["to_stop"] = v_data["name"]
                current_leg["to_node"] = v_data["name"]

        if current_leg:
            legs.append(current_leg)

        # Add destination waypoint
        dst_node = G.nodes[path[-1][0]]
        waypoints.append([dst_node["latitude"], dst_node["longitude"]])

        # Round duration minutes on all legs
        for leg in legs:
            leg["duration_minutes"] = round(float(leg["duration_minutes"]), 1)

        return {
            "label": label,
            "total_duration_minutes": round(total_duration, 1),
            "total_distance_miles": round(total_distance, 2),
            "total_stops": len(path) - 1,
            "transfers_count": transfers,
            "itinerary_legs": legs,
            "waypoints": waypoints,
        }


cta_route_planner = CTARoutePlanner()
