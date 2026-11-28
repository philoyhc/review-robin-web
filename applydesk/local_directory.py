"""The directory a local run searches (segment AD2X): the people of the
*Recruitment and Selection of Residential Assistants* exercise's three
panels, written out as data so the people search keeps them whatever
becomes of the sample exercises. `directory._local_users` puts Cordware's
fake accounts first, then these. Names and addresses are invented.
"""

from __future__ import annotations

#: (name, email), each address once.
PEOPLE: tuple[tuple[str, str], ...] = (
    # The current RAs.
    ("Aisha Bello", "aisha.bello@example.edu"),
    ("Divya Petrova", "divya.petrova@example.edu"),
    ("Quinn Carter", "quinn.carter@example.edu"),
    ("Yuki Farouk", "yuki.farouk@example.edu"),
    ("Mateo Rahman", "mateo.rahman@example.edu"),
    ("Wei Raman", "wei.raman@example.edu"),
    ("Vera Sato", "vera.sato@example.edu"),
    ("Priya Okafor", "priya.okafor@example.edu"),
    ("Divya Sato", "divya.sato@example.edu"),
    ("Chen Carter", "chen.carter@example.edu"),
    ("Divya Novak", "divya.novak@example.edu"),
    ("Bea Novak", "bea.novak@example.edu"),
    ("Ben Novak", "ben.novak@example.edu"),
    ("Omar Farouk", "omar.farouk@example.edu"),
    ("Ivan Raman", "ivan.raman@example.edu"),
    ("Umar Rahman", "umar.rahman@example.edu"),
    ("Hana Okafor", "hana.okafor@example.edu"),
    ("Mateo Carter", "mateo.carter@example.edu"),
    ("Aisha Raman", "aisha.raman@example.edu"),
    ("Farah Petrova", "farah.petrova@example.edu"),
    ("Umar Wei", "umar.wei@example.edu"),
    ("Vera Huang", "vera.huang@example.edu"),
    ("Wei Byrne", "wei.byrne@example.edu"),
    ("Xavier Duarte", "xavier.duarte@example.edu"),
    ("Yuki Wei", "yuki.wei@example.edu"),
    ("Zara Huang", "zara.huang@example.edu"),
    ("Arjun Byrne", "arjun.byrne@example.edu"),
    ("Bea Duarte", "bea.duarte@example.edu"),
    ("Caleb Wei", "caleb.wei@example.edu"),
    ("Dina Huang", "dina.huang@example.edu"),
    # Office staff.
    ("Grace Lim", "grace.lim@example.edu"),
    ("Daniel Ong", "daniel.ong@example.edu"),
    ("Farida Hassan", "farida.hassan@example.edu"),
    ("Marcus Wee", "marcus.wee@example.edu"),
    ("Irene Goh", "irene.goh@example.edu"),
    # Residential staff.
    ("Dr Hana Ito", "hana.ito@example.edu"),
    ("Dr Omar Aziz", "omar.aziz@example.edu"),
    ("Dr Ruth Kahn", "ruth.kahn@example.edu"),
    ("Dr Sara Ng", "sara.ng@example.edu"),
    ("Prof Ivan Petrov", "ivan.petrov@example.edu"),
    ("Dr Mei Lin", "mei.lin@example.edu"),
    ("Dr Tom Reyes", "tom.reyes@example.edu"),
    ("Dr Asha Nair", "asha.nair@example.edu"),
    ("Dr Ken Sato", "ken.sato@example.edu"),
    ("Dr Lucy Park", "lucy.park@example.edu"),
    ("Ms Joy Tan", "joy.tan@example.edu"),
    ("Mr Ravi Das", "ravi.das@example.edu"),
    ("Ms Nora Lee", "nora.lee@example.edu"),
)
