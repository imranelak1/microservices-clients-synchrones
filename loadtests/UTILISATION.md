# Campagne commune aux deux registres

## Mesures isolées sous Linux

Le workflow GitHub Actions `Clients synchrones — deux registres isolés` lance un runner public distinct pour Eureka et Consul. Chaque campagne est contenue dans le même budget Docker de 4 CPU et 8 Gio. L’option `smoke=true` vérifie rapidement les trois clients avec des petits paliers ; ses fichiers portent le suffixe `smoke` et sont exclus de la comparaison. Avec `smoke=false`, chaque méthode reçoit une pile neuve, cinquante appels d’échauffement puis les cinq paliers de 30 s. Les trois pannes réelles suivent : Voiture, registre et Client.

Pour reproduire un profil sans Actions, construire ses jars, puis l’image et la campagne dans un environnement Linux disposant des ports 19260 à 19263 :

```sh
mvn -Peureka clean verify
docker build -f loadtests/runner.Dockerfile -t clients-benchmark-runner .
docker run --rm --network host --cpus=4 --memory=8g -v "$PWD:/work" -w /work -e DISCOVERY_MODE=eureka clients-benchmark-runner python3 loadtests/run_campaign.py
```

Pour Consul, reconstruire avec `-Pconsul` et remplacer `DISCOVERY_MODE=eureka` par `DISCOVERY_MODE=consul`. L’agent Consul réel 1.20.6 est lancé dans le conteneur de mesure ; aucune base de données n’est nécessaire. Les binaires JMeter et Consul sont téléchargés depuis leurs éditeurs et vérifiés par checksum lors de la construction. Les résultats sont écrits sous `results/remote-REGISTRE/IDENTIFIANT/`, avec les logs, données brutes compressées, ressources, événements de panne et limites cgroup. Les artefacts Actions expirent après un jour. Aucune capture ou page de résultats n’est générée par ce driver.

## Exécution locale manuelle

Les captures utilisent Client sur 19263, Voiture sur 19262 et Eureka sur 19261. Après `mvn -Peureka clean package`, lancer les trois jars dans des terminaux séparés :

```sh
java -Xmx160m -XX:ActiveProcessorCount=2 -jar eureka-server/target/eureka-server-1.0.0.jar --server.port=19261
java -Xmx160m -Xss512k -XX:MaxMetaspaceSize=160m -XX:ActiveProcessorCount=2 -Dhttp.maxConnections=500 -jar service-voiture/target/service-voiture-1.0.0.jar --server.port=19262 --spring.profiles.active=eureka --eureka.client.service-url.defaultZone=http://localhost:19261/eureka/ --eureka.instance.ip-address=host.docker.internal
java -Xmx160m -Xss512k -XX:MaxMetaspaceSize=160m -XX:ActiveProcessorCount=2 -Dhttp.maxConnections=500 -jar service-client/target/service-client-1.0.0.jar --server.port=19263 --spring.profiles.active=eureka --eureka.client.service-url.defaultZone=http://localhost:19261/eureka/ --eureka.instance.ip-address=host.docker.internal
```

Attendre les deux applications UP dans Eureka, puis vérifier les trois routes avant la charge. Pour Consul, arrêter ces processus, démarrer `docker compose -f compose-consul.yml up -d`, reconstruire avec `mvn -Pconsul clean package` et relancer les deux applications avec `--spring.profiles.active=consul --spring.cloud.consul.port=19260 --spring.cloud.consul.discovery.ip-address=host.docker.internal`, en conservant les autres options JVM et les ports. Cette dernière adresse permet au health check de l’agent Docker Desktop de joindre les applications de la machine hôte. La capture Consul montre les deux services passing.

Avant chaque méthode, redémarrer les deux applications, attendre leur enregistrement et appeler cinquante fois la route choisie. Les mesures comparent ainsi des JVM neuves avec le même échauffement ; la RSS d’une méthode ne reprend pas l’historique de la campagne précédente. Le registre reste actif pendant les trois méthodes.

Les deux modes enregistrent la même adresse `host.docker.internal` pour les applications. Le trajet HTTP vers Voiture reste ainsi identique : la comparaison ne change pas simultanément le registre et l’adresse réseau du service appelé.

```bash
jmeter -n -t loadtests/clients.jmx -l results/eureka-rest.jtl -Jmethod=rest -Jport=19263
jmeter -n -t loadtests/clients.jmx -l results/eureka-feign.jtl -Jmethod=feign -Jport=19263
jmeter -n -t loadtests/clients.jmx -l results/eureka-webclient.jtl -Jmethod=webclient -Jport=19263
```

Le plan parcourt 10, 50, 100, 200 et 500 utilisateurs : 30 secondes par palier dont 10 secondes de montée. Après reconstruction avec `mvn -Pconsul clean package`, redémarrer les deux services en profil Spring `consul`, attendre les health checks passing et répéter les trois commandes en nommant les sorties `consul-*.jtl`.

Les propriétés `duration`, `rampUp` et `threads1` à `threads5` permettent de vérifier le plan rapidement. Le serveur renvoie toujours le même JSON de 3 070 octets avec un délai de 20 ms. RestTemplate et Feign ont une connexion limitée à 3 s et une lecture limitée à 5 s ; WebClient applique une limite globale de 5 s à l’appel synchrone. JMeter attend au maximum 6 s.

Pour reproduire les mesures, utiliser les mêmes options pour les deux applications et les deux registres : `-Xmx160m -Xss512k -XX:MaxMetaspaceSize=160m -XX:ActiveProcessorCount=2 -Dhttp.maxConnections=500`. La dernière propriété augmente le cache de connexions persistantes du JDK : sa [valeur par défaut de cinq connexions](https://docs.oracle.com/javase/8/docs/technotes/guides/net/http-keepalive.html) provoquait beaucoup de fermetures dans l’essai préparatoire. Elle concerne les clients utilisant `HttpURLConnection`. JMeter utilise `-Xmx192m -Xss256k -XX:ActiveProcessorCount=2`. Les applications restent compilées pour Java 17.

Les fichiers `.jtl.gz` contiennent les résultats bruts compressés, sans suppression des erreurs. `performance.csv` donne les cinq paliers, le taux d’erreur, le débit total et le débit des réponses réussies. Les CSV `*-resources.csv` contiennent les mesures CPU et RSS chaque seconde. Le CPU « machine » divise le pourcentage exprimé sur un cœur par le nombre de processeurs logiques enregistré dans `*-environment.json`, soit quatre sur les runners retenus. La RSS comprend le tas Java et la mémoire native. Les instants sont des timestamps Unix en millisecondes.
