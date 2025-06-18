USE sugrp203;

-- Brugere
CREATE TABLE IF NOT EXISTS Bruger (
    bruger_id INT AUTO_INCREMENT PRIMARY KEY,
    cpr VARCHAR(20) NOT NULL, -- kryptering fjernet, almindelig CPR
    navn VARCHAR(100) NOT NULL,
    pin_kode_hash VARCHAR(255) NOT NULL,
    oprettet_dato DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Sessioner
CREATE TABLE IF NOT EXISTS Session (
    id INT AUTO_INCREMENT PRIMARY KEY,
    bruger_id INT NOT NULL,
    session_token VARCHAR(255) NOT NULL,
    udløbs_tidspunkt DATETIME NOT NULL,
    FOREIGN KEY (bruger_id) REFERENCES Bruger(bruger_id)
);

-- Ve-registreringer
CREATE TABLE IF NOT EXISTS VeRegistrering (
    ve_id INT AUTO_INCREMENT PRIMARY KEY,
    bruger_id INT,
    start_tidspunkt DATETIME NOT NULL,
    slut_tidspunkt DATETIME NOT NULL,
    varighed INT, -- i sekunder
    interval_til_naeste INT, -- i sekunder
    FOREIGN KEY (bruger_id) REFERENCES Bruger(bruger_id)
);

-- Noter
CREATE TABLE IF NOT EXISTS Noter (
    noter_id INT AUTO_INCREMENT PRIMARY KEY,
    bruger_id INT,
    tidspunkt DATETIME NOT NULL,
    noter_type VARCHAR(50),
    beskrivelse TEXT,
    FOREIGN KEY (bruger_id) REFERENCES Bruger(bruger_id)
);

-- Behandlingslog
CREATE TABLE IF NOT EXISTS BehandlingsLog (
    log_id INT AUTO_INCREMENT PRIMARY KEY,
    bruger_id INT,
    handling VARCHAR(100),
    detaljer TEXT,
    tidspunkt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

