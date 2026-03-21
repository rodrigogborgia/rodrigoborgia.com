import React from "react";
import "./long-testimonials.css";

const longTestimonials = [
  {
    text:
      "Fue un gusto contar con tu colaboración. El proceso de elaboración del taller fue muy profesional, supiste entender muy bien nuestra necesidad y ajustarte a la agenda desafiante que teníamos. Los resultados fueron muy  buenos: cumplimos el doble objetivo de sorprender con la dinámica y de llegar a resultados muy interesantes.",
    author: "VICTORIA ACOSTA",
    position: "Gerente Senior de Relaciones Institucionales y Marketing, VEOLIA"
  },
  {
    text:
      "¡Gracias Rodrigo por acercarnos la posibilidad de abordar el trabajo el equipo inter áreas y de una forma tan lúdica como esta! Estamos muy contentos con la jornada.",
    author: "PAULA MATTIELLO",
    position: "Chief Branding Officer, VASSER"
  },
  {
    text:
      "No habíamos utilizado antes Lego Serious Play y realmente fue una excelente dinámica reflexiva y divertida para un equipo con muchos colaboradores. Mediante el juego y los desafíos que se fueron planteando salieron temas muy interesantes y les permitió a algunos salir de su zona de confort y se animaron a participar.",
    author: "ANDREA FISSORE",
    position: "Recursos Humanos, Rosental Inversiones"
  },
  {
    text:
      "La experiencia con Rodrigo ha sido una gran aporte para el equipo de BREMEN. La dinámica logra un clima en el que surgen gran cantidad de oportunidades para trabajar los distintos aspectos de las relaciones.",
    author: "JÁLID DEL AZAR",
    position: "Gerente General, BREMEN TOOLS"
  }
];

export default function LongTestimonialsSection() {
  return (
    <section className="long-testimonials-section">
      <h2 className="long-testimonials-title">Testimonios de mis clientes</h2>
      <div className="long-testimonials-list">
        {longTestimonials.map((t, idx) => (
          <blockquote key={idx} className="long-testimonial-card">
            <span className="long-testimonial-quote">“</span>
            <p>{t.text}</p>
            <footer>
              <strong>{t.author}</strong>
              <span> — {t.position}</span>
            </footer>
          </blockquote>
        ))}
      </div>
    </section>
  );
}
