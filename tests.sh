curl -X POST http://127.0.0.1:5000/ \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "url=https://docs.google.com/document/d/1MrwaV9xBTl08QnFNx6xdvmmRLdpmPpMiwOBpV5k0Hvc/edit?tab=t.0" \
  --data-urlencode "title=Mislandia: Book 1 : The Friendship Begins.pdf" \
  --data-urlencode "storyteller_names=Alyssa Smith, Arione Douglas-Richey, Corey Hopkins, Demi Clemons, Jackson Davis" \
  --data-urlencode "director_name=Mrs. Franklin" \
  --data-urlencode "dedication=We would like to dedicate this book to friendship.
  " \
  -o "output.pdf"