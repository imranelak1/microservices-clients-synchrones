# Comparaison des trois clients synchrones

## Conditions de mesure

La [campagne Linux](https://github.com/imranelak1/microservices-clients-synchrones/actions/runs/38670504936) utilise Java 17, Spring Boot 3.2.12 et JMeter 5.6.3. Eureka et Consul disposent chacun d’un runner AMD EPYC 7763, avec le même budget Docker de 4 CPU et 8 Gio. Les limites cgroup et les configurations sont conservées dans les résultats.

Chaque méthode repart avec une pile neuve et cinquante appels d’échauffement. Chaque JVM dispose de 160 Mio de tas et de deux processeurs visibles. Voiture renvoie le même JSON de 3 070 octets après 20 ms, sans base de données. Les six essais couvrent 10/50/100/200/500 utilisateurs : 30 s par palier, dont 10 s de montée. L’adresse des services reste 127.0.0.1.

Le cache persistant JDK est fixé à 500 connexions. Les commandes et délais des clients sont dans [le protocole](../loadtests/UTILISATION.md). Les essais courts et pilotes Windows sont exclus de ces tableaux.

## Latence et débit

Moyenne, P95 et premier débit correspondent à 100 utilisateurs. Le maximum est recherché parmi les cinq paliers. Les 2 533 626 appels de charge ont réussi.

| Registre | Méthode | Moyenne ms | P95 ms | Succès/s à 100 | Maximum succès/s | Erreurs à 500 % |
|---|---|---:|---:|---:|---:|---:|
| Eureka | RestTemplate | 23.6 | 29 | 3525.8 | 4304.0 | 0.0 |
| Eureka | Feign | 23.7 | 29 | 3520.6 | 4242.8 | 0.0 |
| Eureka | WebClient | 24.8 | 31 | 3360.8 | 4295.6 | 0.0 |
| Consul | RestTemplate | 24.1 | 30 | 3462.8 | 4344.9 | 0.0 |
| Consul | Feign | 23.6 | 29 | 3532.8 | 4275.5 | 0.0 |
| Consul | WebClient | 24.4 | 30 | 3420.3 | 4270.8 | 0.0 |

À 100 utilisateurs, RestTemplate et Feign partagent le meilleur P95 sous Eureka ; Feign obtient 29 ms sous Consul. Les écarts restent faibles, avec un seul passage par cas. Aucun registre ne domine systématiquement. Les caches évitent un accès au registre pour chaque appel. Le générateur partage aussi le budget CPU : ces débits décrivent cette configuration.

## CPU et mémoire

Mesures à 200 utilisateurs, dans l’ordre Client / Voiture. Le CPU est normalisé sur les quatre processeurs logiques. La RSS inclut la mémoire native. Les relevés chaque seconde couvrent également 100 et 500 utilisateurs.

| Registre | Méthode | CPU moyen % Client / Voiture | RSS maximale Mio Client / Voiture |
|---|---|---:|---:|
| Eureka | RestTemplate | 41.08 / 25.72 | 381.66 / 315.79 |
| Eureka | Feign | 41.92 / 25.72 | 376.33 / 348.54 |
| Eureka | WebClient | 43.51 / 24.52 | 393.55 / 312.22 |
| Consul | RestTemplate | 39.61 / 27.55 | 395.25 / 313.67 |
| Consul | Feign | 42.66 / 26.09 | 384.08 / 352.83 |
| Consul | WebClient | 43.53 / 24.85 | 402.88 / 304.75 |

## Pannes observées

Chaque scénario vise 100 requêtes/s pendant 65 s : arrêt demandé à 5 s, redémarrage à 20 s. « Durée arrêt » mesure l’intervalle entre arrêt confirmé et demande de relance. Le premier succès mesure ensuite la fin réelle d’une réponse, démarrage compris. Les triplets suivent RestTemplate / Feign / WebClient ; les erreurs couvrent les 65 s.

| Registre | Processus arrêté | Durée arrêt s | Échecs % | Premier succès après relance s |
|---|---|---:|---|---|
| Consul | Voiture | 14.82 | 29.49 / 29.49 / 29.5 | 4.43 / 4.43 / 4.43 |
| Consul | Client | 12.9 | 29.35 / 29.4 / 29.36 | 4.59 / 4.59 / 4.99 |
| Consul | Registre | 14.99 | 55.47 / 55.51 / 55.49 | 0.0 / 0.01 / 0.02 |
| Eureka | Voiture | 11.81 | 31.06 / 31.06 / 31.12 | 5.37 / 5.37 / 5.37 |
| Eureka | Client | 9.85 | 30.13 / 30.13 / 30.15 | 4.94 / 4.94 / 5.39 |
| Eureka | Registre | 14.91 | 0.42 / 0.42 / 0.46 | 0.0 / 0.01 / 0.02 |

Les deux caches maintiennent 100 % des appels pendant la coupure du registre. Après relance, Eureka subit 28 échecs transitoires. Avec l’agent Consul dev, les appels échouent à partir de 28,93 s ; les deux applications ont dû être relancées pour retrouver leurs inscriptions passing. Les succès à 0 s correspondent donc aux réponses en cache. Voiture indisponible provoque des 503 ; Client arrêté provoque des erreurs de connexion.

## Lisibilité et choix

| Client | Configuration initiale | Lignes dédiées approximatives | Lecture |
|---|---|---:|---|
| RestTemplate | Bean, load balancing, délais | 6 | Appel direct |
| Feign | Starter, activation, interface | 6 + activation | Contrat bref |
| WebClient | Builder, load balancing | 4 | Chaîne et `block()` |

Ces comptes portent sur les fragments compacts, hors DTO et injections partagés ; le formatage les modifie. Je choisirais Feign pour maintenir ce contrat simple. WebClient reste synchrone ici ; son intérêt serait différent dans une application non bloquante.

Les 30 groupes, 6 pannes et JTL bruts sont versionnés. Les [tests HTTP](../evidence/remote-junit/) passent dans les deux profils : cinq tests par profil. Les captures locales montrent les deux enregistrements et les trois réponses identiques.
