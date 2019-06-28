Product Name
DANIERE Benjamin - benjamin.daniere@gmail.com

Geocode_rpls

Geocode_rpls.py est un outil permettant de géocoder les informations du RPLS (Répertoire des logements locatifs des bailleurs Sociaux), disponible sur le site internet data.gouv.fr : https://www.data.gouv.fr/fr/datasets/repertoire-des-logements-locatifs-des-bailleurs-sociaux/

Dans un premier temps, cet outil permet le chargement de données géographique sur la thématique du bâti :
     - via le chargement d'une couche shapefile (.shp)
     - via la lecture d'une table Postgis
     - via la récupération de l'information depuis le serveur d’OpenStreetMap (Sachant que la récupération d'un territoire important est assez chronophage)
    
(Actuellement, cette donnée n'est pas utilisée - des fonctionnalités complémentaires sont en cours de développement pour rattacher ces adresses aux bâtiments les plus proches, selon certaines conditions)

Dans un second temps, l'outil permet de traiter un fichier RPLS (au format csv) :
     - Lecture et filtre d'un fichier RLPS au format csv
     - Prétraitements pour améliorer la qualité des données a géocoder
     - Géocodage des informations via le géocodeur du gouvernent (https://api-adresse.data.gouv.fr)
     - Post-traitement des données produites

Dans un dernier temps, cet outil permet de générer un Dashboard de synthèse des traitements effectués 
     - Diagramme du décompte des données en entrés / traitées 
     - Diagramme des opérations de prétraitements des données 
     - Diagramme du type de précision des résultats du géocodage
     - Diagramme de répartition (/cumulée) des indices de précision des résultats du géocodage  
     - Cartographie simple du résultat du géocodage


Installation des requirements:
Le fichier requirement.txt contient les libraires et leur version à installer pour faire tourner les différentes fonctions.
Vous devez installer ces libraires dans votre environnement virtuel (tel que Anaconda). Pour ce faire, utilisez la commande suivante: Pour ce faire, utilisez la commande suivante:

     pip install -r requirements.txt   ou   conda install --yes --file requirements.txt
     

Préparation du fichier de paramétrage :
Le fichier param.json permet à l'utilisateur de définir les différents paramètres nécessaire au bon déroulement de la chaine de traitement
     - La clé "global" permet de définir le code EPSG de sortie pour les différents résultats de nature géographiques 
     - La clé "data" permet de définir le chemin vers le fichier csv du RPLS et les différents codes INSEE a prendre en compte
          Elle permet également de choisir la méthode de chargement des données bâtiment dans l'outil. En fonction du choix de l'utilisation, il conviendra de renseigner les valeurs du choix


Comment lancer l'outil ?     
     
     python geocode_RPLS.py
     
Les résultats des traitements seront disponible dans le sous-dossier "output" du projet
